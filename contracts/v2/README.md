# contracts/v2: scheduling API contract (P1–P2)

Provider: Claude (backend). Consumer: Codex (web). Version: see `fixtures/index.json` → `contract_version`.

**Generated files. Do not edit by hand.** The source is `api/v2/schemas.py` and `api/v2/routes.py`. Rebuild with `python -m api.v2.contract_build`. `tests/test_contracts_v2.py` fails if these files are out of date.

## Files

- `openapi.json`: OpenAPI 3.1 for every P1–P2 endpoint, including all error responses. Suitable for client generation, e.g. `openapi-typescript`. Generated clients live under `web/` and belong to Codex.
- `fixtures/index.json`: every fixture, with its operation, status and response schema name.
- `fixtures/<name>.json`: `{name, operation_id, method, path, persona, request, response: {status, schema, body}}`. Each body is validated against its schema at build time and in tests.

## Synthetic dataset

- Org "Spice Route Kitchens" with outlets Indiranagar, Koramangala and HSR Layout, all in `Asia/Kolkata`.
- Five skills: Grill, Prep, Server, Cashier, Barista.
- 13 Indiranagar employees. Ravi Kumar has his Saturday shift locked. Rohit Verma is a student who can't work past 21:00 on weekdays.
- Personas: `owner`, `manager_indiranagar` and `staff_ravi`.
- Week of 19 Oct 2026: published version 3, 60 shifts, 0 hard violations.
- Week of 26 Oct 2026: empty, used for the generate and run fixtures.

IDs are stable UUIDv5 values, so the same entity has the same ID in every fixture.

The roster in the fixtures is built by a simple rule-respecting script, not the real solver. Its metrics (coverage, cost, preferred deficits) are computed from its shifts, so they agree with each other within a fixture. Real values will differ.

## Rules the UI can rely on

- **Session transport**: every call except `POST /v2/session/demo` sends `Authorization: Bearer <access_token>`.
  - In the public synthetic demo, the UI gets the token from `POST /v2/session/demo {persona}`. That call returns the token, its expiry and `me`.
  - Private deployments return 403 there and use real sign-in, which is not in this contract yet.
  - Keep the token in memory. On a 401, return to persona selection.
  - Never put admin credentials or database URLs in frontend environment variables.
- **Capabilities**: `me.capabilities` says which controls to show, for example `publish` or `view_costs`. Hiding a control is not authorization; the server re-checks every action.
- **Roster rows**: `ScheduleWeek.employees` lists the rows to draw. A row with no shift on a day means the employee is off that day. An open shift (`employee_id: null`) is an unfilled requirement. `absences` marks leave and sickness, and only `confirmed` absences invalidate an overlapping shift.
- **Trace IDs**: `error.trace_id`, when present, should be shown in "report a problem" details.
- **Errors**: always `{"error": {code, message, retryable, details}}`, including 422. `message` is safe to display. Branch on `code`, never on the message text.
- **Concurrency**:
  - Writes carry `base_revision`, `base_demand_revision` or `base_version_id`. A stale value returns `409 stale_version`, with the current value in `details`.
  - POSTs carry an `Idempotency-Key` header. Replaying a key returns the original result. Reusing a key with a different body returns `409 idempotency_conflict`.
- **Generation is asynchronous**: `POST …/generate` → `202` with a run in `queued`. Poll `GET /v2/optimization-runs/{id}`, waiting `poll_after_ms` between calls, until `poll_after_ms` is null. The schema enforces these combinations:

  | `job_state` | `solver_status` | Meaning / what the UI shows |
  |---|---|---|
  | `succeeded` | `OPTIMAL` | Candidates, each with `proven_optimal: true` |
  | `succeeded` | `FEASIBLE` | Valid candidates, but the time limit stopped the search before optimality was proven |
  | `succeeded` | `INFEASIBLE` | `infeasibility.shortages` and no candidates |
  | `succeeded` | `UNKNOWN` | No solution found in time. This does **not** mean the roster is impossible; say so |
  | `failed` | (any) | `error` |
  
- A candidate never has hard violations. Its full roster is `GET /v2/schedule-versions/{draft_version_id}`.
- **Coverage**: `coverage_ratio` measures cover against **preferred** staffing and can't be inflated by overstaffing. It is `null` when there is no demand. Hard-minimum shortfall is reported separately as `minimum_deficit_minutes`.
- **Time and money**:
  - Instants are ISO 8601 with offset. Display them in the outlet's `timezone`.
  - Recurring times are minutes from local midnight, and Monday is weekday 0.
  - Money is integer paise (`amount_paise`). Format it for display only, and treat the server's numbers as authoritative.
- **Shift identity**: diff versions on `logical_shift_id`. `id` changes with every version.

## Status

All routes are declared but return `501 not_implemented` until B1.2 and B2.3 land. Build against the fixtures until then. Request missing fields or flows through a handoff note; a contract change bumps `contract_version`.
