# Campus Customs: Multi-Agent Operations (HW5)

An agent team that runs a small Yale merch shop. Five pydantic-ai agents (**Boss, Inventory, Accounting, Facilities, Customer Service**) work the shop's tickets using an **MCP server** over a SQLite database. A **FastAPI** backend runs them, and a **React** "Command Bridge" lets a human watch the agents live and approve or reject every payment, discount, purchase and customer message. Agents only *propose*; a human click is the only thing that moves cash.

```
React board (frontend/, :5173) ──HTTP──► FastAPI (backend/main.py, :8000)
                                             │  pydantic-ai agent team (backend/team.py, gpt-6-luna via Portkey)
                                             ▼
                                  MCP server (mcp_server/server.py, FastMCP, stdio)
                                             ▼
                                  data/campus_customs_new.db  (working copy)
```

## Requirements
- Python **3.10+**, Node **18+** (npm), and a **Portkey API key** with access to `gpt-6-luna`.
- macOS/Linux commands below. On Windows use `.venv\Scripts\python` instead of `.venv/bin/python`.

## 1. One-time setup
```bash
git clone <this repo> hw5 && cd hw5

# Python: one venv for the MCP server, the agents and the API
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Secrets: copy the template and paste your Portkey key (the real .env is never committed)
cp .env.example .env          # then edit .env: PORTKEY_API_KEY=...

# React board
cd frontend && npm install && cd ..
```

## 2. Databases: original vs working copy
| File | Role |
|---|---|
| `data/campus_customs.db` | **Original** shop data. Never written to. |
| `data/campus_customs_new.db` | **Working copy.** Agents and approvals write here. As committed, it holds the end state of my full three-ticket run (checking $160, all 3 tickets resolved), which matches `output/desk_tickets.html` and `output/resolved_tickets.json`. |

**For a clean run, copy the original over the working copy:**
```bash
cp data/campus_customs.db data/campus_customs_new.db
```
(When the backend is running you can do the same thing with the board's **⟲ Reset** button or `curl -X POST http://localhost:8000/api/reset`.)

## 3. Start the MCP server
The MCP server (`mcp_server/server.py`, 16 tools) speaks MCP over **stdio**, so it runs as a child process of whatever connects to it:
- **The backend starts it automatically** from `.mcp.json` when it boots (step 4). You don't need a separate terminal.
- To start it by hand or check it works:
  ```bash
  .venv/bin/python mcp_server/server.py          # starts and waits for an MCP client on stdin (Ctrl-C to stop)
  .venv/bin/python mcp_server/smoke_test.py --db data/campus_customs.db --out /tmp/mcp_smoke.json
  ```
  The smoke test connects as a real MCP client, calls the three ticket tools, and checks every value against SQLite.
- **Claude Code / Cursor**: `.mcp.json` at the project root registers it as `campus-customs` (relative paths), so opening the project there lets the chat call the tools directly.

## 4. Start the FastAPI backend
```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000      # or: source ../.venv/bin/activate && uvicorn main:app --reload --port 8000
```
Backend at **http://localhost:8000** (check: `curl http://localhost:8000/api/health`). It allows the Vite origin `http://localhost:5173`.

| Route | What it does |
|---|---|
| `GET /api/tickets` | the 3 tickets, open/resolved |
| `POST /api/tickets/{id}/run` | run the agent team on one ticket (marks it resolved when the run finishes) |
| `GET /api/events` | recent agent events: who said what, which tools (the board polls this) |
| `GET /api/approvals` | proposals waiting for a human |
| `POST /api/approvals/{id}/approve` · `/reject` | human decision; approving a payment/purchase is the **only** thing that changes cash |
| `GET /api/cash` | checking balance from `cash_accounts` |
| `POST /api/reset` | restore the working DB from the original |

## 5. Start the React board
In a second terminal:
```bash
cd frontend
npm run dev            # opens http://localhost:5173
```
Type your name in **Desk officer** (every approval is signed), pick a ticket, and click **Dispatch the Council**. The lightsaber in the top bar switches between Jedi (light/blue) and Sith (dark/red).

## 6. Full three-ticket run (reset first!)
1. **Reset the database** so the run starts clean: board **⟲ Reset**, or `cp data/campus_customs.db data/campus_customs_new.db` (with the backend stopped), or `curl -X POST http://localhost:8000/api/reset`. Checking should read **$3,400.00**.
2. Run **101**, **102**, **103** from the board (about 15–30 s each). Watch the seats and the Transmissions feed. Each ticket gets a RESOLVED stamp when its run finishes.
3. Decide the proposals under **Awaiting Your Seal**. All three money requests total $3,504 against $3,400, so not everything can be paid. My run approved the overdue invoice ($840) and rent ($2,400), and rejected the $264 restock, ending at **$160** (see the Cash tab in `output/desk_tickets.html`).

CLI alternative (no board): `.venv/bin/python backend/run_team.py --all`.

## Layout
```
hw5/
├── AI_prompts.md            my prompts, per problem
├── requirements.txt         one venv: fastmcp, pydantic-ai, fastapi, uvicorn, dotenv
├── .env.example             PORTKEY_API_KEY template (real .env is git-ignored)
├── .mcp.json                MCP server registration (relative paths)
├── data/                    campus_customs.db (original), campus_customs_new.db (working copy)
├── mcp_server/              server.py (FastMCP, 16 tools), db.py (SQL), smoke_test.py, README.md
├── backend/                 main.py (FastAPI), team.py (agent runtime), models.py, agents/ (5 role specs),
│                            prompts/ (boss, inventory, accounting, facilities, customer_service .md), audit.py, config.py
├── frontend/                React + Vite + TypeScript board
└── output/                  harness.md, mcp_smoke.json, desk_tickets.html, design.md,
                             resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt
```

Start with **`output/harness.md`**: it documents the tables, MCP tools, agents, API routes, dashboard and safety rules. **`output/desk_tickets.html`** (double-click) has expected vs actual per ticket, the reconciled cash, and the reflection.
