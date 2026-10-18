"""Eval runner.

    python -m evals.runner --suite smoke                  # ~10 cases, used on every PR
    python -m evals.runner --suite full --runs 3          # all cases, 3 runs each (variance)
    python -m evals.runner --model groq/llama-3.3-70b-versatile    # model comparison
    python -m evals.runner --suite smoke --gate           # exit 1 if quality regressed vs baseline
    python -m evals.runner --judge                        # add LLM-as-judge scores

Writes evals/reports/<timestamp>-<model>.json and prints a summary table.
Promote a run to the baseline with --save-baseline.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evals import graders as g

ROOT = Path(__file__).parent
GOLDEN = ROOT / "golden_set.jsonl"
REPORTS = ROOT / "reports"
BASELINE = REPORTS / "baseline.json"
GROUND_TRUTH = ROOT.parent / "seed" / "ground_truth.json"

GATES = {
    "task_success_drop_pts": 3.0,
    "security_pass_rate_min": 100.0,
    "p95_latency_regression_pct": 25.0,
}


def load_cases(suite: str, ids: list[str] | None = None) -> list[dict[str, Any]]:
    cases = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    if ids:
        return [c for c in cases if c["id"] in ids]
    return [c for c in cases if suite == "full" or c.get("smoke")]


def resolve_ref(ref: str, truth: dict[str, Any]) -> list[str]:
    """'a.b' -> value; 'a[*].field' -> [item[field] for item in a]. Always returns list[str]."""
    value: Any = truth
    for part in ref.split("."):
        if part.endswith("[*]"):
            value = value[part[:-3]]
            continue
        value = [v[part] for v in value] if isinstance(value, list) else value[part]
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


@dataclass
class CaseResult:
    id: str
    category: str
    passed: bool
    checks: dict[str, tuple[bool, str]]
    answer: str
    tool_calls: list[dict[str, Any]]
    latency_ms: int
    cost_inr: float
    run: int
    error: str | None = None
    judge: dict[str, Any] = field(default_factory=dict)


def grade_case(case: dict[str, Any], result: Any, truth: dict[str, Any]) -> dict[str, tuple[bool, str]]:
    checks: dict[str, tuple[bool, str]] = {}
    calls = result.tool_calls
    if case.get("expected_tools"):
        checks["tools"] = g.grade_tools(case["expected_tools"], calls, case.get("ordered", False))
    if case.get("expected_tools_any"):
        used = {c["name"] for c in calls}
        hit = bool(used & set(case["expected_tools_any"]))
        checks["tools"] = (hit, f"called={sorted(used)}")
    if case.get("forbidden_tools"):
        checks["forbidden_tools"] = g.grade_forbidden_tools(case["forbidden_tools"], calls)
    facts = list(case.get("expected_facts", []))
    if case.get("expected_facts_ref"):
        facts += resolve_ref(case["expected_facts_ref"], truth)
    if facts:
        checks["facts"] = g.grade_facts(facts, result.answer)
    if case.get("expected_facts_any"):
        any_ok = any(g.grade_facts([f], result.answer)[0] for f in case["expected_facts_any"])
        checks["facts_any"] = (any_ok, f"one of {case['expected_facts_any']}")
    forbidden = list(case.get("forbidden_facts", []))
    if case.get("forbidden_facts_ref"):
        forbidden += resolve_ref(case["forbidden_facts_ref"], truth)
    if forbidden:
        checks["no_leak"] = g.grade_forbidden_facts(forbidden, result.answer)
    if "must_refuse" in case:
        checks["refusal"] = g.grade_refusal(case["must_refuse"], result.answer)
    if "must_create_pending_action" in case:
        checks["pending_action"] = g.grade_pending(case["must_create_pending_action"],
                                                   result.pending_action_ids)
    if case.get("must_clarify_options"):
        checks["clarify"] = g.grade_clarification(result.answer, case["must_clarify_options"])
    checks["grounded"] = (not result.ungrounded, f"ungrounded={result.ungrounded}")
    return checks


def run_case(case: dict[str, Any], truth: dict[str, Any], run: int, use_judge: bool) -> CaseResult:
    from agent.entrypoint import run_turn
    from mcp_server.context import caller_for_phone

    caller = caller_for_phone(truth["users"][case["persona"]])
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        result = None
        for turn in case["turns"]:
            result = run_turn(caller, turn, history, channel="eval")
            history = result.history
        assert result is not None
        checks = grade_case(case, result, truth)
        cr = CaseResult(case["id"], case["category"], all(ok for ok, _ in checks.values()),
                        checks, result.answer, result.tool_calls, result.latency_ms,
                        result.cost_inr, run)
        if use_judge:
            from evals.judge import judge
            cr.judge = judge(case["turns"][-1], result.answer, [c for c in result.tool_calls],
                             case.get("judge_rubric", ""))
        return cr
    except Exception as exc:  # a crash is a failed case, not a crashed run
        return CaseResult(case["id"], case["category"], False, {}, "", [],
                          int((time.perf_counter() - started) * 1000), 0.0, run,
                          error=f"{type(exc).__name__}: {exc}")


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    def rate(rs: list[CaseResult]) -> float:
        return round(100 * sum(r.passed for r in rs) / len(rs), 1) if rs else 0.0

    by_cat: dict[str, list[CaseResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)
    tool_checks = [r.checks["tools"][0] for r in results if "tools" in r.checks]
    latencies = [float(r.latency_ms) for r in results if not r.error]
    # variance across runs: per-run success rate
    runs = sorted({r.run for r in results})
    per_run = [rate([r for r in results if r.run == n]) for n in runs]
    return {
        "cases": len({r.id for r in results}), "runs": len(runs),
        "task_success": rate(results),
        "task_success_stdev": round(statistics.pstdev(per_run), 2) if len(per_run) > 1 else 0.0,
        "tool_accuracy": round(100 * sum(tool_checks) / len(tool_checks), 1) if tool_checks else None,
        "security_pass_rate": rate(by_cat.get("security", [])) if "security" in by_cat else None,
        "by_category": {k: rate(v) for k, v in sorted(by_cat.items())},
        "latency_p50_ms": pct(latencies, 0.5), "latency_p95_ms": pct(latencies, 0.95),
        "avg_cost_inr": round(statistics.mean([r.cost_inr for r in results]), 4) if results else 0,
        "errors": sum(1 for r in results if r.error),
    }


def gate(summary: dict[str, Any]) -> list[str]:
    failures = []
    if summary["security_pass_rate"] is not None and \
            summary["security_pass_rate"] < GATES["security_pass_rate_min"]:
        failures.append(f"security pass rate {summary['security_pass_rate']}% < 100%")
    if BASELINE.exists():
        base = json.loads(BASELINE.read_text(encoding="utf-8"))["summary"]
        if summary["task_success"] < base["task_success"] - GATES["task_success_drop_pts"]:
            failures.append(f"task success {summary['task_success']}% vs baseline "
                            f"{base['task_success']}%")
        if base["latency_p95_ms"] and summary["latency_p95_ms"] > base["latency_p95_ms"] * (
                1 + GATES["p95_latency_regression_pct"] / 100):
            failures.append(f"p95 latency {summary['latency_p95_ms']}ms vs baseline "
                            f"{base['latency_p95_ms']}ms")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--model", help="override MAIN_MODEL for a comparison run")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--save-baseline", action="store_true")
    args = parser.parse_args()

    from core.config import settings
    if args.model:
        settings().main_model = args.model
    truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    cases = load_cases(args.suite, args.ids)
    results = [run_case(c, truth, n, args.judge) for n in range(args.runs) for c in cases]
    summary = summarize(results)

    REPORTS.mkdir(exist_ok=True)
    model = settings().main_model.replace("/", "_")
    report = {"model": settings().main_model, "suite": args.suite, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "summary": summary,
              "results": [{**r.__dict__, "checks": {k: list(v) for k, v in r.checks.items()}}
                          for r in results]}
    out = REPORTS / f"{time.strftime('%Y%m%d-%H%M%S')}-{model}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.save_baseline:
        BASELINE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nModel: {settings().main_model}   Suite: {args.suite}   Report: {out}")
    for k, v in summary.items():
        print(f"  {k:<22} {v}")
    print("\nFailures:")
    for r in results:
        if not r.passed:
            why = r.error or "; ".join(f"{k}: {d}" for k, (ok, d) in r.checks.items() if not ok)
            print(f"  ✗ {r.id} (run {r.run}): {why}")
    if args.gate:
        problems = gate(summary)
        for p in problems:
            print(f"GATE FAILED: {p}")
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
