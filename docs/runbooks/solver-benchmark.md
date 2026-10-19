# Solver benchmark (B2.4)

Measured 19 October 2026 with `python -m evals.scheduling.benchmark`. Raw reports are in `benchmarks/`:
- `2026-10-19-w8.json`: 8 workers, 10 runs per outlet.
- `2026-10-19-w4.json`: 4 workers, 5 runs per outlet.

The numbers depend on the recorded hardware: Windows 11, 16 logical CPUs, Python 3.14.0, OR-Tools 9.15.6755.

## Setup

- **Benchmark week:** the seeded world for the week of 26 October 2026. That's 3 outlets × 20 employees (60 in total), 5 skills, 30-minute demand from 10:00 to 23:00, and 3 shift templates with fixed breaks.
- **Generation is per outlet,** so latency is reported per outlet solve. The model per outlet has 84 candidate slots, about 560 assignment variables and about 2,000 constraints.
- **Single solve:** the `balanced` strategy with a 3 s limit, repeated with seeds 1..N.
- **Three-candidate generation:** `balanced`, `lowest_cost` and `max_coverage`, each deduplicated and validated, with a 9 s total budget.
- **Baseline:** the documented greedy roster (`seed.world.build_roster`), which is feasible with 0 hard violations under the same validator.

## Results (8 workers, the default)

| Outlet | Single solve p50 / p95 | Status (10 runs) | 3 candidates |
|---|---|---|---|
| Indiranagar | ~0.42 s / 0.58 s | 10 × OPTIMAL, gap 0 | ~1.6 s, OPTIMAL |
| Koramangala | ~0.44 s / 0.56 s | 10 × OPTIMAL, gap 0 | ~1.6 s, OPTIMAL |
| HSR Layout | ~0.48 s / 0.53 s | 10 × OPTIMAL, gap 0 | ~1.4 s, OPTIMAL |

All outlets together: **p95 ≈ 0.58 s**, which meets the under-3 s target. These figures exclude API and UI time.

**With 4 workers the target is missed:** p95 is 3.3 s, every solve hits its time limit with a relative gap of about 40%, and a 30 s limit does not close it. CP-SAT's 4-worker portfolio lacks the bound-improving strategies that prove optimality here. **The default is therefore 8 solver workers** (`api/v2/generation.py`, `scheduling/solver.py`), so a worker host must give each solve at least 8 cores. Size containers accordingly (B6.3).

## Optimizer vs baseline: the cost/coverage trade-off, stated honestly

| Outlet | Roster | Coverage (vs preferred) | Preferred shortfall | Labour cost |
|---|---|---|---|---|
| Indiranagar | Greedy baseline | 0.7714 | 6,570 staff-min | ₹74,700 |
| | Optimizer, matched coverage | 0.7714 | 6,570 | **₹68,805 (−7.9%)** |
| | Optimizer, `balanced` | **0.8883** | 3,210 | ₹81,165 (+8.7%) |
| Koramangala | Greedy baseline | 0.7714 | 6,570 | ₹75,345 |
| | Optimizer, matched coverage | 0.7714 | 6,570 | **₹68,872 (−8.6%)** |
| | Optimizer, `balanced` | **0.8800** | 3,450 | ₹80,355 (+6.6%) |
| HSR Layout | Greedy baseline | 0.7714 | 6,570 | ₹74,408 |
| | Optimizer, matched coverage | 0.7714 | 6,570 | **₹68,775 (−7.6%)** |
| | Optimizer, `balanced` | **0.8883** | 3,210 | ₹81,053 (+8.9%) |

"Matched coverage" is the cheapest roster whose preferred shortfall is no worse than the baseline's (`solve(..., max_shortfall_staff_minutes=...)`). It is proven OPTIMAL.

All rosters have 0 hard violations, checked by the independent validator.

How to read this:
- At equal coverage, the optimizer is about 8% cheaper.
- With the default balanced weights, it buys about 15% more coverage of preferred staffing for about 9% more cost.

**Do not quote the balanced result as a cost saving.** `tests/test_solver.py::test_matched_coverage_is_never_more_expensive_than_the_baseline` guards the matched-coverage result.

## Not measured here

- End-to-end API and UI latency, and absence-to-proposal latency (B4, I4).
- Concurrent load on one worker host.
- Container CPU limits.
- Manager time saved or acceptance rates. Those need human-use evidence and are not claimed.
