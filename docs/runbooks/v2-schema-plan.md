# v2 schema, migration and legacy plan (B0.2)

Status: plan for B1.1 (18 October 2026, Claude). Written against `db/models.py`, `db/init.py`, `db/session.py`, `core/auth.py` and `seed/load.py` at baseline `392fc5a`. Table and column names below are binding for B0.3 contracts and B1.1 migrations unless a later revision of this file changes them.

## 1. Findings in the current schema

| Finding | Consequence for v2 |
|---|---|
| Schema is created with `Base.metadata.create_all` plus RLS DDL in `db/init.py`. There is no migration history. | Existing databases are of unknown shape. Alembic must start from a baseline that reproduces this schema exactly, and an existing database is stamped only after it is verified to match (§4). |
| All foreign keys are single-column (`outlet_id → outlets.id`). | Nothing in the database stops a row in org A from referencing an employee in org B. RLS hides other tenants' rows from reads but does not validate foreign-key targets. v2 tables use composite `(org_id, x_id)` keys (§3). |
| `outlets.slug` is unique across all tenants, and so is `pending_actions.idempotency_key`. | This leaks across tenants and collides when per-session demo orgs are cloned (B6.2). Both need to become per-org uniques. |
| `employees` has one `job_role` string, an `outlet_id`, and no hours limits, tags or skills. | Extend the table additively. Skills move to `employee_skills`, backfilled from `job_role`. |
| `shifts` uses `day` + local `time` columns and a mutable `version` integer. `attendance.shift_id` and payroll depend on it. | Do not reshape it. v2 scheduling uses new tables. v1 `shifts` stays as frozen payroll and attendance history. |
| `audit_log` has no target, before or after fields. Updates are revoked, deletes are not. | Extend it additively and revoke `DELETE` as well. |
| `tenant_session` sets `app.org_id` and `app.user_id` but not `app.role` (roadmap decision 14). | Add `app.role`. RLS still keys on `app.org_id`, and outlet authorization stays in services. |
| `organizations` has no timezone. Outlets have one (`Asia/Kolkata` default). | Add `organizations.timezone`. Outlet timezone governs display and the shift grid. |
| `seed.load` truncates every table, and `/sandbox/reset` calls it. | B1.3 replaces this with tenant-scoped reset. Whole-database seeding becomes an explicit development-only command. |
| `GRANT … ON ALL TABLES` runs once at init time. | Tables created later get no grants. Each migration must grant explicitly, or set `ALTER DEFAULT PRIVILEGES` once. |

## 2. Legacy directories (confirms the roadmap statuses)

| Directory | Contents | v2 status |
|---|---|---|
| `agent/` | LangGraph graph, LiteLLM client, verifier | **Frozen.** B5.1/B5.2 may extract the model-calling part of `agent/llm.py` into `commands/llm.py`. The graph is not extended. |
| `mcp_server/` | v1 read tools, deduction proposals, `actions.decide` | **Frozen.** Its tests remain in the suite while the code exists. `actions.py` is a pattern reference only; v2 approvals live in `approvals/` and `schedule_proposals`. |
| `rag/` | `ingest.chunk_markdown`, used by `seed.load` for policy docs | **Frozen.** The v2 seed must not depend on it. |
| `jobs/` | Empty package (docstring only) | **Frozen placeholder.** The v2 solver worker lives in `scheduling/worker.py` (`python -m scheduling.worker`) with a Postgres-backed queue (§3.5). No Redis or Arq unless measured need justifies it. Notifications can use `jobs/` later. |
| `voice/`, `importer/` | Empty packages | `voice/` is frozen. `importer/` is reused by B5.4 for CSV import. |
| v1 tables (payroll, tips, checklists, policy, conversations, pending_actions) | Live v1 data | Kept unchanged and still covered by RLS. No drops until a v2 replacement is verified and the user approves the removal. |

## 3. v2 tables

Conventions for every table below:

- `org_id uuid not null`.
- RLS policy `tenant_isolation` with both `USING` and `WITH CHECK` on `app.org_id`.
- Grants to `shiftpilot_app` in the same migration.
- Every parent referenced by a v2 child gets `UNIQUE (org_id, id)`, and children reference `(org_id, parent_id)`. This applies to v1 `outlets`, `employees` and `users` too (additive).
- Instants are `timestamptz`. Recurring local times are minutes from local midnight (`smallint`). Durations are integer minutes. Money in scheduling tables is integer paise (`bigint`). Rates stay `Numeric(12,2)` in `employees` and are converted to paise when snapshotted.

### 3.1 Organization and people

- `organizations`: add `timezone text not null default 'Asia/Kolkata'`.
- `outlets`: replace the global unique on `slug` with `UNIQUE (org_id, slug)`. Add `operating_hours jsonb` (per weekday, list of `[open_min, close_min]`, overnight allowed).
- `employees`: add these columns, all nullable or defaulted so v1 rows stay valid:
  - `max_weekly_minutes int` (absolute cap)
  - `regular_weekly_minutes int` (overtime threshold)
  - `preferred_weekly_minutes int`
  - `tags text[] not null default '{}'`
  - `cross_outlet_eligible bool not null default false`
  - `overtime_allowed bool not null default false`
  
  `outlet_id` remains the home outlet.
- `skills (id, org_id, name, UNIQUE(org_id, name))`. Demand, shifts and templates all reference a skill. In v2 a "role" such as cashier or server is a skill a shift requires.
- `employee_skills (org_id, employee_id, skill_id, level smallint, PK(employee_id, skill_id))`.

### 3.2 Availability, absence, preferences, travel

- `employee_availability (id, org_id, employee_id, weekday smallint 0–6, start_minute, end_minute, kind available|preferred|unavailable, valid_from date, valid_to date null)`. Recurring and outlet-local. Overnight windows are represented with `end_minute > 1440`.
- `absences (id, org_id, employee_id, start_at, end_at, kind leave|sick|other, status requested|confirmed|rejected|cancelled, reported_by_user_id, source manager|employee|import, reason text null, created_at)`. These are operational facts (decision 5) and never edit a version.
- `employee_preferences (id, org_id, employee_id, preference_type, value jsonb, weight smallint)`.
- `travel_times (org_id, from_outlet_id, to_outlet_id, minutes, PK(from, to))`. The value is a configured estimate (decision 10).

### 3.3 Policy, templates, demand

- `scheduling_policies (id, org_id, outlet_id null, revision int, min_rest_minutes default 600, grid_minutes default 30, default_regular_weekly_minutes default 2880, default_max_weekly_minutes, daily_ot_threshold_minutes, ot_multiplier_bp, break_rules jsonb, effective_from)`. A `null` outlet means the org default. A new revision is a new row; history is kept for snapshot reproducibility.
- `shift_templates (id, org_id, outlet_id, skill_id null, name, start_minute, duration_minutes, break_minutes, active)`. This is the solver's search space (decision 3).
- `demand_bands (id, org_id, outlet_id null, skill_id, min_orders, max_orders null, staff_minimum, staff_preferred)`.
- `demand_inputs (org_id, outlet_id, interval_start timestamptz, orders int, source history|scenario|manual)`.
- `staffing_requirements (id, org_id, outlet_id, skill_id, interval_start, interval_end, minimum_required, preferred_required, source band|manual|scenario, demand_revision int, UNIQUE(outlet_id, skill_id, interval_start))`. These are 30-minute intervals and are the solver's input. Minimum is hard and preferred is penalized (decision 1).
- `scheduling_rules (id, org_id, scope jsonb, rule_type, parameters jsonb, hard bool, priority, source_text, status draft|active|archived, created_by, revision)` (B5.2). The compiled form is validated before it becomes `active`.

### 3.4 Schedules and immutable versions

- `schedules (id, org_id, outlet_id, week_start date, current_version_id null, UNIQUE(org_id, outlet_id, week_start))`. There is one row per outlet-week. `current_version_id` points at the live **published** version.
- `schedule_versions` has these columns, with `UNIQUE(schedule_id, version_number)`:
  - `id, org_id, schedule_id, version_number`
  - `status draft|published|superseded|discarded`
  - `base_version_id null`
  - `source seed|manual|generate|optimize|repair|restore|import`
  - `reason text`, `optimization_run_id null`
  - `created_by_user_id null` (null means the system)
  - `approved_by_user_id null`, `created_at`, `published_at null`
  - `input_hash`
- `logical_shifts (id, org_id, schedule_id, created_in_version_id)`. Each row is a stable shift identity across versions, so diffs report "moved" or "reassigned" rather than delete-plus-insert.
- `version_shifts` has these columns:
  - `id, org_id, version_id, logical_shift_id, outlet_id`
  - `employee_id null` (null means an open, unfilled shift)
  - `skill_id, start_at, end_at, break_minutes`
  - `locked bool`, `lock_reason null`, `template_id null`
  - `UNIQUE(version_id, logical_shift_id)`

Rules:

- **Immutability.** A trigger rejects `INSERT/UPDATE/DELETE` on `version_shifts` when the parent version's status is not `draft`. A trigger also rejects `schedule_versions` updates other than these transitions: `draft → published | discarded` and `published → superseded`. The app role has no `DELETE` on either table.
- **Live roster** means the `version_shifts` of each schedule's `current_version_id`. Superseded and draft rows are never counted as employee commitments. Organization-wide conflict checks (overlap, rest, travel, weekly caps) read the current versions of every outlet, including adjacent weeks (decision 4).
- **Within-version overlap guard (optional, decided in B1.1).** A `btree_gist` exclusion constraint on `(version_id, employee_id, tstzrange(start_at, end_at))`. It is defence in depth only; the validator remains authoritative because rest, travel and cross-version checks cannot be expressed this way.
- **Publication** (B3.2) runs in one transaction:
  1. Lock the affected `schedules` rows `FOR UPDATE` in stable id order.
  2. Lock the affected employees' current shifts.
  3. Check that each `current_version_id` still equals the proposal's base version and that the input hash still matches.
  4. Re-run the validator against the organization-wide live roster.
  5. Mark the old version `superseded` and the new one `published`, and move the pointer.
  6. Write audit and outbox rows.
- **Restore** copies an old version's shifts into a new draft, validates it against current facts (absences, availability) and goes through normal publication. History is never rewritten.

### 3.5 Runs, candidates, proposals

- `optimization_runs` has these columns:
  - `id, org_id, kind generate|optimize|repair`
  - `outlet_ids uuid[]`, `base_version_ids uuid[]`, `requested_by_user_id`
  - `idempotency_key`, with `UNIQUE(org_id, idempotency_key)`
  - `job_state queued|running|succeeded|failed|cancelled`
  - `solver_status OPTIMAL|FEASIBLE|INFEASIBLE|MODEL_INVALID|UNKNOWN null`
  - `input_hash`, `input_snapshot jsonb`, `config jsonb` (strategy, time limit, workers, seed, ortools version)
  - `attempts`, `lease_owner`, `lease_until`
  - `queued_at, started_at, finished_at, solver_wall_ms`
  - `objective`, `best_bound`, `stats jsonb` (variable and constraint counts), `error jsonb`
  
  Job state and solver status are separate, and approval state lives on proposals (decision 7).
- **Worker.** It claims runs with `UPDATE … WHERE id = (SELECT id … WHERE job_state='queued' OR (job_state='running' AND lease_until < now()) ORDER BY queued_at FOR UPDATE SKIP LOCKED LIMIT 1)`, solves in a bounded process pool, and renews its lease while solving. An expired lease after a crash is reclaimed, with bounded `attempts`. Durable state is never held only in memory.
- `optimization_candidates (id, org_id, run_id, rank, strategy, solver_status, objective_components jsonb, metrics jsonb, diff jsonb, draft_version_id, validation jsonb, explanation_facts jsonb, dedup_hash, UNIQUE(run_id, dedup_hash))`. Each candidate's schedule is a draft `schedule_version`, so review, edit and publish share one path.
- `schedule_proposals` has these columns:
  - `id, org_id, candidate_id null, draft_version_ids uuid[]`
  - `base_version_ids uuid[]`, `input_hash`
  - `status pending|approved|rejected|expired|stale|failed`
  - `required_role`, `requested_by_user_id`
  - `decided_by_user_id null`, `decided_at null`, `expires_at`
  - `idempotency_key`, with `UNIQUE(org_id, idempotency_key)`
  - `result jsonb null`
  
  The approval flow reuses the v1 pattern with its gaps fixed: authorization is checked **before** a terminal replay, decision and audit commit together, and stale base versions are rejected.
- `audit_log`: add nullable `action`, `target_type`, `target_id`, `before jsonb`, `after jsonb`. Revoke `DELETE` from the app role. v1 columns are unchanged.

### 3.6 Later migrations (named now so contracts can reserve shapes)

- `employee_requests` (B5.3): availability changes, leave, absence and swap requests. These are requests, never direct schedule writes.
- `import_jobs`, `import_rows` (B5.4): staged rows with a TTL, committed in one transaction.
- Demo sessions (B6.2): **each public demo session is its own cloned synthetic organization**. Isolation then comes from the same RLS and composite keys as every tenant. TTL cleanup deletes that org's rows, and reset can never reach another org. This is why `outlets.slug` must be unique per org.

## 4. Migration mechanics

Alembic lives in `db/migrations/`, with `alembic.ini` at the repo root using the admin URL. The app role never runs migrations.

| Revision | Content |
|---|---|
| `0001_v1_baseline` | The exact current schema: tables, indexes, extensions, app role, grants, RLS and the audit revoke, as produced today by `db.init`. It is verified by comparing a fresh `upgrade 0001` database with a fresh `db.init` database (reflected schema and `pg_policies`) in a test. |
| `0002_tenant_hardening` | Adds `UNIQUE(org_id, id)` on outlets, employees and users; makes `outlets.slug` per-org; adds the org timezone; extends audit columns and revokes `DELETE`; sets default privileges. |
| `0003_scheduling_core` | §3.1–3.5 tables (runs, candidates and proposals included, merged from the planned 0004), the immutability triggers, RLS and grants, plus backfilling `skills` and `employee_skills` from `employees.job_role`. |
| `0004+` | Rules, employee requests, imports, demo sessions, as each phase needs them. |

**Existing databases.** `python -m db.migrate adopt` handles a database that has v1 tables but no `alembic_version`:

1. Reflect the database.
2. Compare it with revision `0001` (tables, columns, types, constraints and RLS policies).
3. Stamp `0001` **only if they are identical**. Otherwise it refuses and prints the differences.

Then `alembic upgrade head` runs as usual. A database is never stamped blind.

**Populated upgrade test.** B1.1 acceptance seeds v1 data with the current `seed.load`, adopts the database, upgrades to head, and asserts:
- every v1 row count and payroll ground-truth figure is unchanged;
- the existing integration suite still passes;
- the new tables are RLS-isolated for the runtime role.

**`db.init`** becomes a thin wrapper around `alembic upgrade head` once 0001 lands. `create_all` is no longer used outside tests.

**v1 shift data.** v1 shifts are not converted into v2 versions automatically, because the only existing data is synthetic demo payroll history. The v2 seed (B1.3) generates its own schedules. If a real tenant appears, a one-off converter that creates a `published` version with `source=import` would be added. It is not built speculatively.

## 5. Session context and authorization

- `tenant_session` sets `app.org_id`, `app.user_id` and `app.role` with transaction-local `set_config`.
- Services check outlet scope through `core.auth` before any read or write. A manager is bound to one outlet. Cross-outlet actions (B4.5) need the owner role, enforced in the service and covered by tests.
- Every v2 table gets a second-tenant test with the runtime role, covering both read invisibility and a rejected cross-tenant insert via composite foreign keys.

## 6. Conventions handed to B0.3 contracts

- Instants: RFC 3339 with offset. Display timezone: the outlet's `timezone`.
- Recurring times: minutes from local midnight.
- Durations: integer minutes.
- Money: integer paise plus `currency: "INR"`. Display rounding is the client's job and is not authoritative.
- Grid: shift start and end must fall on the policy grid (default 30 minutes) in outlet local time.
- IDs are UUID strings.
- Every mutating request carries an `Idempotency-Key` header. Every proposal or publish carries `base_version_id(s)` and `input_hash`.

## 7. Implemented in B1.1 — commands

```sh
python -m db.init                      # upgrade to head; adopts a matching pre-Alembic DB first
python -m db.migrate upgrade           # same, without the adopt step
python -m db.migrate adopt             # verify-then-stamp a db.init-era database as 0001
python -m alembic check                # models and migrations must agree (also tested)
python -m db.init --drop               # DEVELOPMENT ONLY: drop the public schema, then upgrade
```

Acceptance evidence is `tests/integration/test_migrations.py` (fresh upgrade, downgrade/re-upgrade, adopt accepts identical and refuses different schemas, populated v1 upgrade with skill backfill, RLS on v2 tables with the runtime role, composite-key cross-tenant rejection, per-org slugs, version and shift immutability, app-role privileges), plus the unchanged v1 integration suite running on a database adopted from the old `db.init`.
