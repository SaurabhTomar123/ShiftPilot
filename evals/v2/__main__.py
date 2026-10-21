"""Evaluation runner (B6.1, architecture v3 section 42).

    python -m evals.v2                     # everything, offline (scripted language model)
    python -m evals.v2 --suite language --live   # the configured LANGUAGE_MODEL
    python -m evals.v2 --gate              # exit 1 if any case fails

The report is tied to the code and configuration it measured: the git commit (and whether the tree was
dirty) and a hash of the solver weights, repair profiles, prompts, model and OR-Tools version.
Solver quality and language quality are reported separately, never mixed into one number.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "runbooks" / "evals"


def _git() -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        except OSError, subprocess.CalledProcessError:
            return ""

    return {
        "commit": run("rev-parse", "HEAD") or None,
        "dirty": bool(run("status", "--porcelain", "--untracked-files=no")),
    }


def config_hash(model_name: str) -> tuple[str, dict[str, Any]]:
    from api.v2.schemas import CONTRACT_VERSION
    from language import parsing
    from scheduling import repair, solver

    config = {
        "strategies": {k: v.coefficients() for k, v in solver.STRATEGIES.items()},
        "repair_profiles": list(repair.PROFILES),
        "disruption_slack": repair.DISRUPTION_SLACK,
        "prompts": hashlib.sha256((parsing.COMMAND_PROMPT + parsing.RULE_PROMPT).encode()).hexdigest()[:16],
        "language_model": model_name,
        "ortools": version("ortools"),
        "contract": CONTRACT_VERSION,
    }
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    return "sha256:" + digest, config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["all", "scheduling", "language"], default="all")
    parser.add_argument("--live", action="store_true", help="language cases against LANGUAGE_MODEL")
    parser.add_argument("--gate", action="store_true", help="exit 1 when any case fails")
    args = parser.parse_args()

    from evals.v2 import language as lang_cases
    from evals.v2 import scheduling as sched_cases
    from language import adapter
    from language.scripted import ScriptedModel

    model: adapter.Model = adapter.current() if args.live else ScriptedModel()
    model_name = "live" if args.live else "scripted"
    if args.live:
        from core.config import settings

        model_name = settings().language_model or "none"
    results: dict[str, dict[str, Any]] = {}

    def record(suite: str, name: str, ok: bool, detail: str, ms: float) -> None:
        entry = results.setdefault(suite, {"cases": 0, "passed": 0, "failures": [], "ms": 0.0})
        entry["cases"] += 1
        entry["passed"] += int(ok)
        entry["ms"] += ms
        if not ok:
            entry["failures"].append({"case": name, "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {suite:<13} {name:<58} {detail[:70]}", flush=True)

    if args.suite in ("all", "scheduling"):
        for sc in sched_cases.scenarios():
            started = time.perf_counter()
            try:
                ok, detail = sc.run()
            except Exception as exc:  # a crash is a failure, not an aborted report
                ok, detail = False, f"error: {type(exc).__name__}: {exc}"
            record(sc.suite, sc.name, ok, detail, (time.perf_counter() - started) * 1000)
    if args.suite in ("all", "language"):
        for case in lang_cases.cases():
            started = time.perf_counter()
            try:
                ok, detail = case.run(model)
            except adapter.LanguageUnavailable as exc:
                ok, detail = False, f"unavailable: {exc}"
            except Exception as exc:
                ok, detail = False, f"error: {type(exc).__name__}: {exc}"
            record(case.suite, case.name, ok, detail, (time.perf_counter() - started) * 1000)

    digest, config = config_hash(model_name)
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": _git(),
        "config_hash": digest,
        "config": config,
        "suites": {
            k: {**v, "pass_rate": round(v["passed"] / v["cases"], 4), "ms": round(v["ms"])}
            for k, v in results.items()
        },
        "totals": {
            "cases": sum(v["cases"] for v in results.values()),
            "passed": sum(v["passed"] for v in results.values()),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{report['generated_at'][:10]}-{args.suite}-{model_name.replace('/', '_')}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(path.relative_to(ROOT)), **report["totals"], "config_hash": digest}))
    failed = report["totals"]["cases"] - report["totals"]["passed"]
    return 1 if args.gate and failed else 0


if __name__ == "__main__":
    sys.exit(main())
