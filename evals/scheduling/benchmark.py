"""Scheduling benchmark (B2.4): optimizer vs. the greedy baseline, and repeated-run latency.

    python -m evals.scheduling.benchmark                 # writes docs/runbooks/benchmarks/<date>.json
    python -m evals.scheduling.benchmark --runs 20

The benchmark week is the seeded world (3 outlets x 20 employees = 60 employees). Generation is
outlet-scoped, so latency is reported per outlet solve. Each case records solver status and gap, so a
fast but unproven answer is never presented as optimal (roadmap decision 7). Numbers depend on the
hardware recorded in the report.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from scheduling import metrics, solver, validator
from seed import world
from seed.world_snapshot import build, greedy_roster

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "runbooks" / "benchmarks"
TARGET_P95_MS = 3000


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def summarize(m: metrics.Metrics) -> dict[str, Any]:
    return {
        "coverage_ratio": m.coverage_ratio,
        "minimum_deficit_minutes": m.minimum_deficit_minutes,
        "preferred_deficit_minutes": m.preferred_deficit_minutes,
        "labour_cost_paise": m.labour_cost_paise,
        "assigned_minutes": m.assigned_minutes,
        "preference_match_ratio": m.preference_match_ratio,
    }


def run(runs: int, time_limit: float, workers: int) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hardware": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "processor": platform.processor(),
        },
        "config": {
            "runs_per_case": runs,
            "time_limit_seconds": time_limit,
            "workers": workers,
            "ortools": version("ortools"),
            "strategy": "balanced",
            "week": world.NEXT_WEEK.isoformat(),
            "employees_per_outlet": 20,
        },
        "target_p95_ms": TARGET_P95_MS,
        "outlets": {},
    }
    all_single: list[float] = []
    for key, _ in world.OUTLETS:
        snap = build(key, with_bench=True)
        baseline_roster = greedy_roster(key)
        latencies, statuses, gaps = [], [], []
        best: solver.Candidate | None = None
        for seed in range(1, runs + 1):
            started = time.perf_counter()
            status, cand, stats = solver.solve(
                snap, "balanced", time_limit=time_limit, seed=seed, workers=workers
            )
            latencies.append((time.perf_counter() - started) * 1000)
            statuses.append(status)
            if cand:
                gaps.append((cand.objective - cand.bound) / max(1, cand.objective))
                best = best or cand
        started = time.perf_counter()
        full = solver.generate(snap, "balanced", time_limit=time_limit * 3, workers=workers)
        full_ms = (time.perf_counter() - started) * 1000
        all_single += latencies
        assert best is not None, f"{key}: no solution"
        baseline_metrics = metrics.compute(snap, baseline_roster)
        _, matched, _ = solver.solve(
            snap,
            "lowest_cost",
            time_limit=time_limit * 3,
            workers=workers,
            max_shortfall_staff_minutes=baseline_metrics.preferred_deficit_minutes,
        )
        assert matched is not None, f"{key}: no matched-coverage solution"
        report["outlets"][key] = {
            "model": {k: stats[k] for k in ("candidate_slots", "assignment_variables", "constraints")},
            "single_solve_ms": {
                "p50": round(percentile(latencies, 0.5)),
                "p95": round(percentile(latencies, 0.95)),
                "max": round(max(latencies)),
            },
            "statuses": {s: statuses.count(s) for s in sorted(set(statuses))},
            "max_relative_gap": round(max(gaps), 6) if gaps else None,
            "three_candidate_generate": {
                "ms": round(full_ms),
                "status": full.status,
                "candidates": [c.strategy for c in full.candidates],
            },
            "baseline": {
                **summarize(metrics.compute(snap, baseline_roster)),
                "hard_violations": validator.validate(snap, baseline_roster).hard,
            },
            "optimizer": {
                **summarize(metrics.compute(snap, best.roster)),
                "hard_violations": validator.validate(snap, best.roster).hard,
            },
            # Cheapest roster with preferred shortfall <= the baseline's: cost compared at matched coverage.
            "matched_coverage": {
                **summarize(metrics.compute(snap, matched.roster)),
                "hard_violations": validator.validate(snap, matched.roster).hard,
                "status": matched.status,
            },
        }
    report["single_solve_ms_all_outlets"] = {
        "p50": round(percentile(all_single, 0.5)),
        "p95": round(percentile(all_single, 0.95)),
        "meets_target": percentile(all_single, 0.95) < TARGET_P95_MS,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--time-limit", type=float, default=3.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    report = run(args.runs, args.time_limit, args.workers)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{report['generated_at'][:10]}-w{args.workers}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(path.relative_to(ROOT)), **report["single_solve_ms_all_outlets"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
