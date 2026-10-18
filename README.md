# ShiftPilot

**An AI operations agent for restaurants.** Managers ask *"Why did Ravi get less this week?"* or *"Add a ₹150 meal deduction for Ravi K"*. The agent answers from real data through an MCP tool server, never does arithmetic itself, and nothing changes without human approval. Quality is measured by an eval suite that gates CI.

> 🎥 Demo video · 🔗 Live demo · 📊 Eval dashboard — *(add links at M2/M3)*

<!-- Put the 90-second demo GIF here -->

## Results
*(Fill from `python -m evals.runner --suite full --runs 3 --judge` — keep in sync with the latest run.)*

| Model | Task success | Tool accuracy | Security | p50 | p95 | ₹ / conversation |
|---|---|---|---|---|---|---|
| | | | | | | |

## Architecture

```
 Web chat / Voice / WhatsApp ──► FastAPI (auth, approvals) ──► LangGraph agent
                                                               guard → router → executor → verifier → responder
                                                                              │ tool calls (in-process or MCP/HTTP)
                                                                              ▼
                                                         MCP server "restaurant-ops" (9 tools, more in M2)
                                                         role checks · audit log · all maths in core/payroll.py
                                                                              │
                                                         Postgres + pgvector, row-level security per org
```
Key decisions: [docs/design-decisions.md](docs/design-decisions.md) · Security: [docs/threat-model.md](docs/threat-model.md) · Full spec: [REQUIREMENTS.md](REQUIREMENTS.md)

## Quick start (Windows PowerShell)

```powershell
# 1. Python env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env        # then add at least ANTHROPIC_API_KEY (or change MAIN_MODEL)

# 2. Database
docker compose -f infra/docker-compose.yml up -d --wait
python -m db.init             # tables, app role, row-level security
python -m seed.load           # synthetic restaurants + ground_truth.json

# 3. Tests
pytest                        # unit (no DB)
pytest -m integration         # tools against Postgres + RLS

# 4. Try it
python -m mcp_server.server   # MCP over stdio (see Claude Desktop below)
uvicorn api.main:app --reload --port 8000
python -m evals.runner --suite smoke
```

### Use the tools from Claude Desktop
Add to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "restaurant-ops": {
      "command": "C:\\Users\\Saurabh\\shiftpilot\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\Users\\Saurabh\\shiftpilot"
    }
  }
}
```
It acts as `MCP_DEMO_USER_PHONE` (default: Brew Lane Café manager). Ask: *"Who's on the closing shift this Friday?"*

### Call the API
```powershell
$t = (Invoke-RestMethod -Method Post http://localhost:8000/auth/demo-token -ContentType application/json -Body '{"persona":"cafe_manager"}').token
Invoke-RestMethod -Method Post http://localhost:8000/chat -Headers @{Authorization="Bearer $t"} -ContentType application/json -Body '{"message":"Why did Ravi Kumar get less this week?"}'
```
Personas: `owner`, `cafe_manager`, `qsr_manager`, `kitchen_manager`, or `{"phone": "<staff phone from seed/ground_truth.json>"}`.

## Repo map
| Path | What |
|---|---|
| `core/` | payroll engine, anomaly detectors, auth rules, money formatting, PII redaction, JWT |
| `db/` | SQLAlchemy models, RLS setup (`python -m db.init`), tenant sessions |
| `seed/` | deterministic data generator, loader, sample policy, `ground_truth.json` |
| `mcp_server/` | MCP server, tools (read + propose), approval/execution, audit |
| `agent/` | LangGraph graph, prompts, LiteLLM client, grounding verifier, tool bridge |
| `api/` | FastAPI: demo tokens, chat, approvals, sandbox reset |
| `evals/` | golden set, graders, LLM judge, runner with CI gate, iteration log |
| `rag/` | policy chunking + embeddings |
| `voice/`, `jobs/`, `importer/`, `web/` | M4–M6 (plans in each folder) |

## Status
| Milestone | State |
|---|---|
| M1 Data + tools | ✅ 9/12 tools (3 propose_* tools to do), unit tests, integration tests |
| M2 Agent + web | 🟡 agent graph + API done; web UI, streaming, interrupt, MCP HTTP bridge to do |
| M3 Evals | 🟡 runner, graders, judge, CI gate, 26 starter cases; grow to 200 |
| M4 Quality | ⬜ |
| M5 Channels | ⬜ |
| M6 Onboarding + launch | ⬜ |

Search the code for `TODO(M` to find every next step.
