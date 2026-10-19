# Solver benchmark (B2.4)

Measured 19 October 2026 with `python -m evals.scheduling.benchmark`. Raw reports are in `benchmarks/`:
- `2026-10-19-w8.json`: 8 workers, 5 runs per outlet, re-measured with the architecture v3 profile weights (A3.8).
- `2026-10-19-w4.json`: 4 workers, 5 runs per outlet (pre-A3.8 weights).
- `2026-10-19-w8-det2.json`: evaluation mode, deterministic time 2, 8 workers, 3 runs per outlet with one seed.

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
| Indiranagar | ~0.36 s / 0.39 s | 5 × OPTIMAL, gap 0 | OPTIMAL |
| Koramangala | ~0.43 s / 0.47 s | 5 × OPTIMAL, gap 0 | OPTIMAL |
| HSR Layout | ~0.34 s / 0.35 s | 5 × OPTIMAL, gap 0 | OPTIMAL |

All outlets together: **p95 ≈ 0.46 s**, which meets the under-3 s target. These figures exclude API and UI time. (Before A3.8 the p95 was 0.58 s over 10 runs.)

**With 4 workers the target is missed:** p95 is 3.3 s, every solve hits its time limit with a relative gap of about 40%, and a 30 s limit does not close it. CP-SAT's 4-worker portfolio lacks the bound-improving strategies that prove optimality here. **The default is therefore 8 solver workers** (`api/v2/generation.py`, `scheduling/solver.py`), so a worker host must give each solve at least 8 cores. Size containers accordingly (B6.3).

## Optimizer vs baseline: the cost/coverage trade-off, stated honestly

| Outlet | Roster | Coverage (vs preferred) | Preferred shortfall | Labour cost |
|---|---|---|---|---|
| Indiranagar | Greedy baseline | 0.7714 | 6,570 staff-min | ₹74,700 |
| | Optimizer, matched coverage | 0.7714 | 6,570 | **₹68,805 (−7.9%)** |
| | Optimizer, `balanced` | **0.8633** | 3,930 | ₹78,555 (+5.2%) |
| Koramangala | Greedy baseline | 0.7714 | 6,570 | ₹75,345 |
| | Optimizer, matched coverage | 0.7714 | 6,570 | **₹68,872 (−8.6%)** |
| | Optimizer, `balanced` | **0.8633** | 3,930 | ₹78,435 (+4.1%) |
| HSR Layout | Greedy baseline | 0.7714 | 6,570 | ₹74,408 |
| | Optimizer, matched coverage | 0.7714 | 6,570 | **₹68,775 (−7.6%)** |
| | Optimizer, `balanced` | **0.8633** | 3,930 | ₹78,173 (+5.1%) |

"Matched coverage" is the cheapest roster whose preferred shortfall is no worse than the baseline's (`solve(..., max_shortfall_staff_minutes=...)`). It is proven OPTIMAL.

All rosters have 0 hard violations, checked by the independent validator.

How to read this:
- At equal coverage, the optimizer is about 8% cheaper.
- With the v3 Balanced profile (cost 0.25, understaffing 0.30, preferences 0.15, disruption 0.20, hours-preference alignment 0.10), it buys about 9 points more coverage of preferred staffing for about 5% more cost. The pre-A3.8 weights bought about 12 to 15 points for about 9%.

**Do not quote the balanced result as a cost saving.** `tests/test_solver.py::test_matched_coverage_is_never_more_expensive_than_the_baseline` guards the matched-coverage result.

## Profiles and evaluation mode (A3.8)

- **Profiles are v3 weight vectors.** Each one sums to 1 over cost, understaffing, preferences, disruption and hours-preference alignment. Users choose a profile and never see weights. Fixed exchange rates (`scheduling/solver.py`, `UNIT`) turn the shares into integer coefficients. At Balanced, one staff-minute below preferred is worth ₹4 of labour, a shift outside preferred windows ₹20, a changed base assignment ₹50 and a minute away from someone's preferred week 20 paise.
- **Hours-preference alignment is not fairness.** It is Σ|worked − preferred weekly minutes| over employees with a preference, reported as `metrics.hours_preference_deviation_minutes`. It says nothing about who gets the closing shifts.
- **Disruption.** When regenerating over a published version, each base assignment the new roster drops is a disruption. A kept assignment keeps its logical shift id, so candidate diffs show real changes instead of a full replacement.
- **Evaluation mode** (v3 §15): `--deterministic-time N` bounds the search in CP-SAT deterministic time with one seed and interleaved parallel search. Three 8-worker runs per outlet produced **one identical roster per outlet**, all OPTIMAL (`reproducible: true`). It is slow (about 10 s per solve), so it is for evaluations and benchmarks only. Production keeps wall-clock limits, where two runs may legitimately return different valid rosters. A run whose config has `deterministic_time` is reproducible from `input_hash` plus config.

## Not measured here

- End-to-end API and UI latency, and absence-to-proposal latency (B4, I4).
- Concurrent load on one worker host.
- Container CPU limits.
- Manager time saved or acceptance rates. Those need human-use evidence and are not claimed.
