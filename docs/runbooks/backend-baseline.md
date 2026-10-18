# Backend baseline (B0.1)

Recorded 18 October 2026 on branch `claude/backend`, starting from `main` at `a8765c0`. Windows 11, Docker Desktop 29.0.1. Owner: Claude.

## Runtime decision (roadmap decision 15)

**Python 3.14** for v2, pinned as `requires-python = ">=3.14,<3.15"` with ruff `py314` and mypy `3.14`.

- 3.14.0 is the only interpreter on the development machine, and the existing `.venv` was already built with it.
- OR-Tools 9.15.6755 publishes 3.14 wheels and is the only OR-Tools release that does. Every other locked dependency resolved and installed on 3.14.
- The full existing suite passes on 3.14 with the locked versions (results below).
- The spec's 3.12 was a default, not a requirement. CI and containers must use 3.14 (for example `python:3.14-slim`).

## Dependencies

- `pyproject.toml` adds `ortools==9.15.6755` (exact pin, because solver behaviour and status semantics are version-sensitive) and `alembic>=1.20,<2`.
- `requirements.lock` is a universal (cross-platform), hash-pinned lock for runtime and `dev` extras. The `voice` extra is v1-only and not locked. Regenerate with:

  ```sh
  python -m uv pip compile pyproject.toml --extra dev --universal --python-version 3.14 --generate-hashes -o requirements.lock
  python -m uv pip install -r requirements.lock
  ```

- `uv` is installed into the venv as a tool. It is not a project dependency.
- On Windows, the VS Code Ruff extension keeps `.venv/Scripts/ruff.exe` open, which makes a ruff upgrade fail with "Access is denied". Rename the old executable (`ruff.exe` → `ruff.exe.old-locked`) and rerun the install, or close VS Code first.

## Verified CP-SAT API (installed 9.15.6755)

Checked with a probe script, not assumed from documentation:

- `CpSolver.status_name()` returns `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID` and `UNKNOWN`. All five constants exist on `cp_model`.
- `objective_value`, `best_objective_bound` and `wall_time` are available after a solve. `parameters.max_time_in_seconds`, `num_workers` and `random_seed` are settable.
- `CpModel.add_assumptions([...])` together with `CpSolver.sufficient_assumptions_for_infeasibility()` returns the conflicting enforcement literals (by variable index) on an infeasible model. This is the basis for decision 9 diagnostics.
- `CpModel.add_hint()` and `CpModel.validate()` work. Hints are the basis for low-disruption repair warm starts.

## Check results

| Check | Command | Result |
|---|---|---|
| Unit tests | `python -m pytest -q` | 33 passed, 10 deselected (integration) |
| Integration tests | `python -m pytest -q -m integration` (env below) | 10 passed |
| Lint | `python -m ruff check .` | clean (ruff 0.17.1) |
| Types | `python -m mypy` (strict, `core` and `mcp_server` only) | clean, 18 files (mypy 2.4.0) |

No baseline failures. Note that mypy covers only `core/` and `mcp_server/`. v2 modules must be added to `[tool.mypy].files` as they are created.

## Integration database: destructive, use a disposable one

The integration fixture runs `db.init` and then `seed.load`, which **truncates every table** in whichever database `DATABASE_URL` points to. The `.env` default is the compose database on port 5433, which uses the persistent `shiftpilot_pgdata` volume. Never run integration tests against it if it holds anything you want to keep.

The Claude lane uses a volume-less container on port 5434:

```sh
docker run -d --rm --name shiftpilot-claude-pg -p 5434:5432 \
  -e POSTGRES_USER=shiftpilot -e POSTGRES_PASSWORD=shiftpilot -e POSTGRES_DB=shiftpilot \
  pgvector/pgvector:pg16
export DATABASE_URL=postgresql+psycopg://shiftpilot:shiftpilot@localhost:5434/shiftpilot
export APP_DATABASE_URL=postgresql+psycopg://shiftpilot_app:shiftpilot_app@localhost:5434/shiftpilot
python -m pytest -q -m integration
docker stop shiftpilot-claude-pg   # --rm discards all data
```

Environment variables take precedence over `.env` (pydantic-settings), so this override is enough. Fixing the destructive global reset is part of B1.3.

## Not verified here

- Live LLM provider access (v1 agent paths). It is not needed for P0–P4 and is checked before B5.1.
- Container builds and CI on 3.14. These come in B6.3.
