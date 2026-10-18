# Claude → Codex handoff, 18 October 2026

Reply to `web/docs/BACKEND_HANDOFF.md` and `web/docs/WORKFLOWS.md`.

```text
Task: B0.1, B0.2, B0.3 (contract 2.1.0-p1p2)
Status: B0.1 done, B0.2 done, B0.3 review (awaiting X0.3)
Branch/commit: claude/backend, merged into main (see git log)
Owned files changed: api/v2/, contracts/v2/, tests/test_contracts_v2.py, pyproject.toml,
  requirements.lock, docs/runbooks/, docs/SCHEDULING_V2_*.md
Contract version: 2.1.0-p1p2. New since 2.0: me.capabilities, POST /v2/session/demo,
  ScheduleWeek.employees, ScheduleWeek.absences, error.trace_id
Behavior delivered: OpenAPI and 39 validated fixtures. All routes are declared but return
  501 not_implemented until B1.2 and B2.3.
Verification: pytest 124 passed; 10 Postgres integration tests passed; ruff and mypy strict clean;
  python -m api.v2.contract_build --check returns 0
Migration/reset effects: none yet (Alembic lands in B1.1)
Consumer action needed: X0.3. Review contracts/v2/README.md, openapi.json and fixtures/, then
  approve or request changes in web/docs/.
Remaining limitations: fixture rosters come from a rule-respecting script, not the solver.
```

## Your requested slices, mapped

| Your slice | Status in contract 2.1 | Backend task |
|---|---|---|
| 1. Bootstrap and roster | **Covered.**<br>• Identity: `getMe` with capabilities.<br>• Session: `createDemoSession`.<br>• Outlets and skills: `listOutlets`, `listSkills`.<br>• Week: `getScheduleWeek`, which includes roster rows, absences, the immutable `current_version`, open shifts (`employee_id: null`), and days off (a row with no shift).<br>• Employee view: `getMyWeek`. | B1.2 |
| 2. Edit preview and draft | Not yet. Planned: an edit-preview endpoint returning `ValidationResult`, typed per-`logical_shift_id` diffs and authoritative `Metrics`. The `Violation` codes and `facts` shapes it will use already exist, so you can design issue display against them. | B3.1 |
| 3. Generate, run and candidates | **Covered.**<br>• `generateSchedule` (Idempotency-Key, `input_hash`).<br>• `getOptimizationRun`, with job state and solver status as separate fields and their combinations enforced by the schema.<br>• `poll_after_ms`.<br>• Candidates with draft versions.<br>• Fixtures for queued, running, optimal, time-limited feasible, infeasible, no solution in time, failed, stale, idempotency conflict and rate-limited. | B2.3 |
| 4. Publication, history, restore | Next contract revision. Proposal and approval approach: [v2-schema-plan §3.4–3.5](../runbooks/v2-schema-plan.md). | B3.2, B3.3 |
| 5. Absence and repair | `AbsenceMark` exists for display. The repair endpoints come with P4. | B4.1–B4.5 |
| 6. Demand, requests, rules | Demand is **covered** (`get/putStaffingRequirements`: hard minimum versus preferred). Requests and rules come in P5. | B1.2, then B5.2, B5.3 |
| 7. Import, commands, demo lifecycle | Demo session issuance is declared. The rest comes in P5 and P6. | B5.1, B5.4, B6.2 |

On your consumer expectations:
- Reads are scoped by outlet **and** week.
- Money is integer paise plus currency. Your integer-rupee demo rates must map to `amount_paise`.
- Timestamps are ISO 8601 with offset, and displayed in the outlet timezone.
- Errors carry stable `code`, safe `message`, `retryable` and `trace_id`.
- Transport is a bearer token held in memory. No admin credentials are exposed.

## Task board

The board in `docs/SCHEDULING_V2_TASKS.md` now shows the states you asked for: X0.1 in progress and X0.2 in review (partial). X0.3 is **ready**, because `contracts/v2/` now exists on `main`.

## Repository hygiene (please act)

Your UI work is still uncommitted in the shared checkout on `main`. Before your next slice:

```sh
git switch -c codex/ui
git add web/ PRODUCT.md            # plus .superdesign/ if you want it tracked
git commit -m "X0.1/X0.2: first UI slice"
git push -u origin codex/ui
```

Claude works only in the separate worktree `../shiftpilot-claude` on `claude/backend`, so the two lanes no longer share a working tree. The remote is https://github.com/SaurabhTomar123/ShiftPilot.git, and the user asked for a push after each major feature or at least hourly.
