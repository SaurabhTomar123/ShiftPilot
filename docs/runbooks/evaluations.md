# Evaluations (B6.1, architecture v3 §42)

    python -m evals.v2                          # everything offline; writes docs/runbooks/evals/<date>-all-scripted.json
    python -m evals.v2 --suite language --live  # language cases against LANGUAGE_MODEL
    python -m evals.v2 --gate                   # exit 1 if any case fails (nightly CI)

Each report records the **git commit** (and whether the tree was dirty) and a **configuration hash** over the solver profile coefficients, repair profiles and disruption slack, the prompts, the language model, the OR-Tools version and the contract version. Two reports with the same hash measured the same configuration. Solver quality and language quality are separate suites and are never combined into one number.

| Suite | Cases | What must hold |
|---|---|---|
| normal | 24 | 3 outlets × 2 weeks × 4 profiles: every candidate passes the independent validator and minimum staffing is kept. |
| impossible | 5 | Demand beyond the qualified headcount: `INFEASIBLE`, shortages reported, a `reduced_minimum` option, and never a candidate. |
| overtime | 5 | Regular hours capped below the need: either a valid roster within the caps, or an `overtime` option. |
| locks | 5 | 1–12 locked shifts survive generation unchanged. |
| repair | 10 | Absences on different days and outlets: the absent person is replaced, the plan is valid, and disruption stays local (≤ 6 changes). |
| rules_enforced | 5 | Latest-end and days-per-week rules bind the people they cover, and the roster validates. |
| multi_outlet | 3 | One outlet short of cooks: a `cross_outlet` option names another outlet's staff, and normal generation never uses them. |
| commands | 17 | Phrasings of time off, sickness, generation and unsupported requests become the right intent and fields. |
| ambiguity | 5 | "Ravi" with two Ravis asks; full names and unique first names resolve; unknown names ask. |
| rule_language | 10 | Supported rules compile to the right type, scope and parameters; unsupported ones are refused. |
| security | 7 | Prompt injection never yields an intent outside the allow-list; tampered model output is rejected by the schema. |

Offline, the language suites use `language.scripted`, a deterministic stand-in, so they check the pipeline (schemas, resolution, refusal). `--live` measures the hosted model with the same cases. CI runs the language and security cases on every push (`tests/test_evals_v2.py`) and the full set nightly.

**Baseline (21 Oct 2026, offline):** 96 of 96 cases pass. The scheduling suites take about 33 s on the reference machine; see the committed report.

Database-level security (tenant isolation, role grants, least-privilege worker and relay) is covered by the integration and fault-injection tests rather than here.
