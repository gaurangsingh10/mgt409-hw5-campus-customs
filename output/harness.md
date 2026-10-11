# Campus Customs Multi-Agent Operations — Harness

The complete spec for **Campus Customs Multi-Agent Operations**: an agent team (Boss, Inventory, Accounting, Facilities, Customer Service) that works the shop's tickets through an MCP server, a FastAPI backend, and a React desk where a human watches and approves.

**Architecture:** React desk (`frontend/`, :5173) → FastAPI (`backend/main.py`, :8000) → pydantic-ai agent team (`backend/team.py`, gpt-6-luna via Portkey) → MCP server (`mcp_server/server.py`, stdio) → SQLite (`data/campus_customs_new.db`). Every shop fact and every write goes through the MCP server.

**Run it:**
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && cp .env.example .env   # once
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000                              # backend + agents + MCP
cd frontend && npm run dev                                       # the desk, opens http://localhost:5173
```

**Contents:** 1 Data · 2 Tickets · 3 Models & runtime · 4 MCP tools · 5 Agents & audit trail · 6 API routes · 7 Dashboard · 8 Safety · 9 Plan vs actual & cash · 10 Files

- **Original data (read-only reference):** `data/campus_customs.db`
- **Working copy (agents read and write here):** `data/campus_customs_new.db`
- **Shop "today":** `2026-08-31` (from `desk.date_today`, which agents use as the date, not the system clock)

---

## 1. Data — tables and fields

### `desk` — shared shop context (1 row)
| Field | Type | Meaning |
|---|---|---|
| `date_today` | TEXT | The shop's current business date |
| `notes` | TEXT | Free-form notes for the day |

**Why it matters:** Every agent needs the same "today" to decide what is overdue or due soon. The Boss reads it first.

### `tickets` — incoming work queue (3 rows, all `open`)
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Ticket number |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override`, … |
| `requester` | TEXT | Customer, landlord, or org that raised it |
| `subject` | TEXT | Short title |
| `sku`, `size`, `qty` | TEXT/TEXT/INT | Product request details (links to `inventory`/`pricing`) |
| `lease_id` | INTEGER FK → `leases.id` | Set when the ticket is about rent or space |
| `invoice_id` | INTEGER FK → `invoices.id` | Set when the ticket depends on a vendor bill |
| `status` | TEXT | `open` → (later) in progress / awaiting approval / closed |
| `notes` | TEXT | Original message text |
| `created_at` | TEXT | ISO timestamp |

**Why it matters:** This is the Boss agent's inbox. `type` decides which specialist gets the ticket, and the FK columns tell that agent which other tables to check.

### `inventory` — stock on hand (10 rows, PK = `sku` + `size`)
| Field | Type | Meaning |
|---|---|---|
| `sku` | TEXT | Product code (e.g. `CC-TEE-WHITE`) |
| `name` | TEXT | Display name |
| `size` | TEXT | S/M/L/XL, or `OS` (one size) |
| `qty` | INTEGER | Units on hand |
| `location` | TEXT | Aisle in the shop |

**Why it matters:** The Inventory agent uses it to answer "can we fill this order?" Two rows are already at 0 (Tee S, Crest Mug).

### `pricing` — cost and price per SKU (4 rows, one per SKU)
| Field | Type | Meaning |
|---|---|---|
| `sku` | TEXT PK | Product code |
| `unit_cost` | REAL | What the shop pays per unit |
| `list_price` | REAL | Normal retail price |

**Why it matters:** Accounting and Customer Service use it to quote prices and to check discount requests against margin (`list_price − unit_cost`).

### `vendors` — suppliers (3 rows)
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Vendor id |
| `name` | TEXT | Vendor name |
| `specialty` | TEXT | What they supply |
| `lead_days` | INTEGER | Days from order to delivery |

**Why it matters:** The Inventory agent picks a vendor to restock from, and `lead_days` tells the customer how long they will wait.

### `invoices` — bills owed to vendors (1 row)
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Invoice number |
| `vendor_id` | INTEGER FK → `vendors.id` | Who billed us |
| `amount` | REAL | Amount owed |
| `due_date` | TEXT | Payment deadline |
| `status` | TEXT | `open` / `paid` |
| `description` | TEXT | What it was for |

**Why it matters:** These are Accounting's payables. An unpaid invoice can hold up a restock that a customer is waiting for.

### `payments` — money that has gone out (0 rows)
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Payment id |
| `kind` | TEXT | `invoice` / `rent` / … |
| `ref_id` | INTEGER | Id of the invoice or lease being paid |
| `amount` | REAL | Amount paid |
| `account` | TEXT | Which `cash_accounts.name` it came from |
| `paid_at` | TEXT | Timestamp |
| `approved_by` | TEXT | **Human approver (required, NOT NULL)** |

**Why it matters:** This is the audit trail. `approved_by` is NOT NULL, so the schema itself requires a human approval behind every payment. Agents can propose payments, but only the dashboard approval can write a row here.

### `cash_accounts` — money available (1 row)
| Field | Type | Meaning |
|---|---|---|
| `name` | TEXT PK | Account (`checking`) |
| `balance` | REAL | Current balance |
| `date` | TEXT | As-of date |

**Why it matters:** Accounting must check the balance before proposing any payment so the shop never overdraws.

### `leases` — the shop's space (1 row)
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Lease id |
| `space_name` | TEXT | Location (`Chapel Street shop`) |
| `landlord` | TEXT | Who we pay |
| `monthly_rent` | REAL | Rent amount |
| `next_due` | TEXT | Next rent due date |
| `notes` | TEXT | Extra terms |

**Why it matters:** The Facilities agent owns rent. Rent competes with vendor invoices for the same cash.

### `approval_requests`: agent proposals for the human (added by the MCP server)
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Request number shown on the dashboard |
| `ticket_id` | INTEGER FK → `tickets.id` | Which ticket produced it |
| `kind` | TEXT | `pay_invoice`, `pay_rent`, `restock_order`, `price_override`, `customer_reply` |
| `ref_id` | INTEGER | Invoice id / lease id being paid |
| `amount`, `unit_price`, `qty`, `vendor_id` | REAL/REAL/INT/INT | Validated against `invoices` / `leases` / `pricing` / `vendors` when filed |
| `message` | TEXT | Draft customer reply text |
| `summary` | TEXT | Agent's one-paragraph case for it |
| `requested_by` | TEXT | Agent that filed it (stamped by the runtime, can't be faked) |
| `status` | TEXT | `pending` → `approved` / `rejected` |
| `decided_by`, `decided_at`, `decision_note` | TEXT | The human who decided, when, and why |

**Why it matters:** This is the hand-off between agents and the human. Agents can only add rows here. Only a human click on the dashboard turns an approved money row into a `payments` row and a lower `cash_accounts.balance`.

### Relationship map
```
tickets.sku/size ──► inventory (sku, size) ──► pricing.sku
tickets.invoice_id ─► invoices.id ──► vendors.id
tickets.lease_id ───► leases.id
payments.ref_id ────► invoices.id | leases.id   (by payments.kind)
payments.account ───► cash_accounts.name
approval_requests.ticket_id ─► tickets.id   (approved money kinds → payments)
```

---

## 2. The three open tickets (as of 2026-08-31)

### Ticket 101: `customer_order`, Tauhid Zaman, Bulldog Tee size S ×1
- **Inventory:** `CC-TEE-WHITE / S` has qty **0**, so we can't ship it today. (M = 5, L = 3, XL = 2 are in stock.)
- **Linked invoice 501:** Bulldog Print Co (vendor 1, 5 lead days), **$840**, "Rush reprint CC-TEE-WHITE S", due **2026-08-28**, status `open`. **It is 3 days overdue.** The restock that would fill this order is tied to an unpaid bill.
- **Price:** $28 list ($8 cost).
- **Agents involved:** Customer Service (reply to the customer), Inventory (no stock; restock depends on the reprint), Accounting (overdue invoice needs payment approval).

### Ticket 102: `rent_notice`, Elm City Properties, "Rent due"
- **Linked lease 1:** Chapel Street shop, **$2,400/month**, next due **2026-09-02** (2 days away).
- **Agents involved:** Facilities (owns the lease), Accounting (cash check), plus human approval for the payment.

### Ticket 103: `price_override`, Yale AI Club, 20 × Hoodie size M with a bulk discount
- **Inventory:** `CC-HOOD-NAVY / M` has only **8**, which is **12 short**. (S 4, L 14, XL 6, total 32 across sizes.)
- **Pricing:** $58 list / $22 cost, so $36 margin per unit. At list price, 20 units = **$1,160**. Even a 30% discount ($40.60/unit) stays above cost.
- **Restock:** Bulldog Print Co (apparel reprint, 5 lead days).
- **Agents involved:** Customer Service (talks to the club), Inventory (shortfall/restock), Accounting (discount vs. margin), and **human approval** for any price override.

### Cash picture across all tickets
| Item | Amount |
|---|---|
| Checking balance | $3,400 |
| Invoice 501 (overdue) | −$840 |
| Rent (due 9/02) | −$2,400 |
| **Left if both are paid** | **$160** |

Both can be paid, but the account would be nearly empty, and any reprint for ticket 103 would add more cost. The Boss and Accounting agents should flag this to the human instead of auto-paying. That's the main reason the approval dashboard exists.

---

## 3. Models & runtime (Problem 5)
- **LLM:** `gpt-6-luna` for **every** agent, through **Portkey** (`PORTKEY_API_KEY` in `HW5/.env`, copied from Lecture 7). The model name is hard-coded in `backend/config.py` so it can't drift.
- **API style:** OpenAI **Responses** API (`OpenAIResponsesModel`). Portkey routes gpt-6-luna to Azure, which **rejects function tools on `/v1/chat/completions`** for this model (`400: Function tools with reasoning_effort are not supported...`). `/v1/responses` allows them.
- **Framework:** pydantic-ai 2.x for the agents and standalone **FastMCP** for the server, in **one** venv (`.venv`, root `requirements.txt`). The server runs as a stdio child process of the backend. (Problems 4–10 originally used two venvs because the old `mcp<2` FastMCP clashed with pydantic-ai's `mcp` 2.x; Problem 11 switched to standalone `fastmcp` so graders install once.)
- **Data types (`backend/models.py`):** `AgentName`, `ApprovalKind`, `ApprovalRef`, `AgentReport` (every agent's structured output: summary, facts tagged by source tool, actions, approvals, needs_human, open questions, next steps), `AuditEntry` (one line of the audit trail), `TeamRunResult`.

---

## 4. MCP tools (`mcp_server/`)

**Server:** `mcp_server/server.py` (FastMCP, name `campus-customs`), with queries in `mcp_server/db.py`.
**Database:** `data/campus_customs_new.db` (working copy). **16 tools:** 12 agent tools (10 read, 2 write) + 4 dashboard/human-only tools. The first three, from Problem 3, are described in detail below because each one unlocks a ticket.
**Rule:** Tools return only values stored in the database, plus plain arithmetic on them (sums, differences, day counts). Missing rows come back as `found: false` with an error message. They are never filled in with guesses.

### `check_stock(sku, size)`
- **Reads:** `inventory` (all sizes of the SKU)
- **Unlocks:** **Ticket 101**, Tauhid Zaman's Classic Bulldog Tee size S
- **Why it's the right tool:** Tauhid's order names an exact SKU and size, and this call shows `CC-TEE-WHITE / S` has `qty_on_hand: 0`. It also returns the in-stock sizes (M 5, L 3, XL 2), so Customer Service can honestly say "S is sold out" and offer a size swap or a wait instead of promising a shirt we don't have.
- **Verified output:** `in_stock: false`, location Aisle B.

### `get_lease_rent_status(lease_id)`
- **Reads:** `leases`, `desk` (shop date), `cash_accounts`
- **Unlocks:** **Ticket 102**, Elm City Properties' rent notice (lease_id 1)
- **Why it's the right tool:** The landlord's email only says "rent due in 2 days." This call confirms it from our own records ($2,400 for Chapel Street, due 2026-09-02, 2 days from the desk date of 2026-08-31) and shows that checking ($3,400) covers it with $1,000 left. That's everything Facilities needs to send a rent payment for human approval.
- **Verified output:** `days_until_due: 2`, `can_cover_rent: true`, `cash_after_rent: 1000.0`.
- **Caveat:** `cash_after_rent` ignores the overdue $840 invoice 501. If both are paid, $160 is left. A later invoice tool will cover that.

### `quote_bulk_order(sku, size, qty)`
- **Reads:** `pricing`, `inventory` (the requested size)
- **Unlocks:** **Ticket 103**, Yale AI Club's request for 20 Hoodies size M at a bulk discount
- **Why it's the right tool:** A discount decision needs both the margin and whether we can deliver. This call shows that 20 hoodies at list price is $1,160 against $440 in cost, that any price under $22/unit (more than 62.1% off) loses money, and that we have only 8 in size M (12 short). The human approver gets the real price floor and the stock gap before saying yes.
- **Verified output:** `shortfall: 12`, `unit_margin_at_list: 36.0`, `max_discount_pct_before_loss: 62.1`.
- **Safety:** This tool reports numbers only. It does not approve or write a discount.

### Connection & smoke test (Problem 4)
- **Config:** `.mcp.json` registers server `campus-customs` (stdio, command `.venv/bin/python mcp_server/server.py`, relative to the project root; the DB path defaults to `data/campus_customs_new.db`). The same entry is in the class-folder `.mcp.json`, which Claude Code loads for this chat.
- **SDK:** standalone `fastmcp` (falls back to the `mcp<2` bundled FastMCP if that's what is installed).
- **Evidence:** `output/mcp_smoke.json`. For each tool it records the prompt, the tool name, the arguments, the raw MCP output, and an independent SQL read of the same values (`matches_db`). Result: **3/3 pass**.

### Full MCP tool list: agent tools (12)
All agents get shop facts **only** through these tools (pydantic-ai `MCPToolset` → stdio → `mcp_server/server.py` → `data/campus_customs_new.db`). There is no second data layer in the backend.

| # | Tool | Tables | R/W | Used by | Ticket it unlocks |
|---|---|---|---|---|---|
| 1 | `check_stock(sku, size)` | `inventory` | R | inventory, customer_service | 101: Tee S = 0, offer M/L/XL |
| 2 | `get_lease_rent_status(lease_id)` | `leases`, `desk`, `cash_accounts` | R | facilities | 102: $2,400 due 09-02, 2 days |
| 3 | `quote_bulk_order(sku, size, qty)` | `pricing`, `inventory` | R | accounting, customer_service | 103: $1,160 list, $22 floor, 12 short |
| 4 | `get_shop_date()` | `desk` | R | all | all: "today" = 2026-08-31 for overdue/due math |
| 5 | `list_open_tickets()` | `tickets` | R | boss | all: the boss's inbox |
| 6 | `get_ticket(ticket_id)` | `tickets` | R | boss, all specialists | all: request details + linked sku / invoice_id / lease_id |
| 7 | `get_invoice(invoice_id)` | `invoices`, `vendors`, `payments`, `desk` | R | accounting, inventory | 101: invoice 501 $840, Bulldog Print Co, 3 days overdue, blocks the S reprint |
| 8 | `list_vendors()` | `vendors` | R | inventory, accounting | 103: Bulldog Print Co, apparel, 5 lead days → est. 09-05 |
| 9 | `get_cash_position()` | `cash_accounts`, `invoices`, `vendors`, `leases`, `desk` | R | boss, accounting, facilities | 101/102/103: $3,400 − $840 − $2,400 = **$160** |
| 10 | `list_approval_requests(status)` | `approval_requests` | R | all | all: avoid duplicate proposals |
| 11 | `update_ticket_status(ticket_id, status, note, agent)` | `tickets` | **W** | boss | all: open → awaiting_approval, with a signed note |
| 12 | `submit_approval_request(...)` | `approval_requests` (validated against `invoices`, `leases`, `pricing`, `vendors`, `tickets`) | **W** | inventory, accounting, facilities, customer_service | 101 pay_invoice + reply, 102 pay_rent, 103 price_override + restock + reply |

### Dashboard / human-only tools (4): in **no** agent's allowlist, called only by `backend/main.py`
| # | Tool | Tables | R/W | Called by route |
|---|---|---|---|---|
| 13 | `list_tickets()` | `tickets`, `approval_requests` | R | `GET /api/tickets` |
| 14 | `human_decide_approval(approval_id, decision, approver, note)` | `approval_requests`, `payments`, `cash_accounts`, `invoices`, `leases`, `tickets` | **W** | `POST /api/approvals/{id}/approve` · `/reject` |
| 15 | `human_resolve_ticket(ticket_id, resolved_by, note)` | `tickets` | **W** | end of `POST /api/tickets/{id}/run` |
| 16 | `human_reset_database()` | whole DB file (copied from `data/campus_customs.db`) | **W** | `POST /api/reset` |

`human_decide_approval` runs as one transaction. It re-reads the invoice or lease amount, refuses to overdraw, writes the `payments` row with `approved_by`, lowers `cash_accounts.balance`, marks the invoice `paid` or moves `leases.next_due` forward a month, and records who decided and why.

**Never exposed to agents:** writing `payments`, changing `cash_accounts`, `inventory.qty` or `pricing`, approving/rejecting, resolving tickets.

---

## 5. The five agents

Code: `backend/team.py` (runtime, loop, delegation, audit), `backend/agents/<role>.py` (role spec: MCP tools + approval rights), `backend/prompts/<role>.md` (prompt in my words). Run: `.venv/bin/python backend/run_team.py 101 | --all`.

**Agent loop:** pydantic-ai `agent.iter()`: model → tool calls (MCP or `delegate`) → tool results → model … → `AgentReport`. Each node is written to the audit trail as it happens.
**Delegation:** every agent has a `delegate(to_agent, task)` tool that can reach **every other agent** (full connectivity), subject to the loop limits above. The child runs its own loop on the same MCP connection and token budget, and its `AgentReport` comes back as the tool result.

| Agent | Role | MCP tools | Can file | Typical delegations |
|---|---|---|---|---|
| **boss** | Triage each ticket, route work, check numbers agree, set status, report to the human | get_shop_date, list_open_tickets, get_ticket, get_cash_position, list_approval_requests, update_ticket_status | — | → inventory / accounting / facilities (facts), then → customer_service (reply, with facts pasted in) |
| **inventory** | Stock by SKU/size, alternatives, shortfalls, vendors & lead times, restock proposals (no double-ordering when a reprint invoice already exists) | get_shop_date, get_ticket, check_stock, list_vendors, get_invoice, list_approval_requests, submit_approval_request | restock_order | → accounting (can we afford it) |
| **accounting** | Cash vs. obligations, invoices & overdue bills, discount/margin math (10% for 10–19, 15% for 20+, never below cost) | get_shop_date, get_ticket, get_cash_position, get_invoice, quote_bulk_order, list_vendors, list_approval_requests, submit_approval_request | pay_invoice, price_override | → inventory (stock behind a deal) |
| **facilities** | Lease & rent, verify landlord notices, rent first but flag the cash squeeze | get_shop_date, get_ticket, get_lease_rent_status, get_cash_position, list_approval_requests, submit_approval_request | pay_rent | → accounting (cash judgment) |
| **customer_service** | Honest, warm 80–150-word drafts; offers real alternatives; never promises unapproved discounts/dates | get_shop_date, get_ticket, check_stock, quote_bulk_order, list_approval_requests, submit_approval_request | customer_reply | → accounting (discount) / inventory (lead time) |

### Audit trail (`output/audit_trail.json`)
Append-only JSON array; one `AuditEntry` per agent-loop step: `ts, team_run_id, run_id, ticket_id, agent, delegated_by, chain, step, event, model, detail, usage`. Events: `run_start` (task), `user_prompt`, `model_response` (text + every tool call with args + token usage), `tool_results` (clipped to 3,000 chars), `delegation` (from/to/task/refused/reused), `run_end` (full `AgentReport` + this run's usage + team total), `error`. Never wiped by a run or a reset. At the end of Problem 9 it holds 436 entries across every run since Problem 5; the Problem 9 runs are entries 336–436.

---

## 6. Backend API routes (`backend/main.py`)
`backend/main.py` (FastAPI). Start from `backend/` with `uvicorn main:app --reload --port 8000` (venv: `../.venv/bin/uvicorn ...`), base URL **http://localhost:8000**. Every route reads/writes shop data through the campus-customs MCP server; CORS allows only localhost origins.

- `GET  /api/health`: server is up, model name, which ticket (if any) the team is working right now.
- `GET  /api/tickets`: all tickets (101, 102, 103) with `state` open/resolved, detailed status and pending-approval count.
- `POST /api/tickets/{id}/run`: run the agent team (boss + delegates) on one ticket and return the boss's report + token usage; when the run succeeds the ticket is marked **resolved** (Problem 8). 409 if a run is already in progress or the ticket is resolved.
- `GET  /api/events?limit=&since=&ticket_id=&team_run_id=&agent=`: recent agent events from `output/audit_trail.json`: what each agent said, the tools it called (with args) and the results, delegations, and final reports. Poll with `since=<latest_ts>` to refresh the board.
- `GET  /api/approvals?status=pending|approved|rejected|all`: agent proposals waiting for (or decided by) a human.
- `POST /api/approvals/{id}/approve` `{approver, note}`: a human approves. For pay_invoice / pay_rent / restock_order this is the **only** path that writes `payments` (approved_by = the human) and lowers the checking balance. It refuses to overdraw and warns under the $500 floor.
- `POST /api/approvals/{id}/reject` `{approver, note}`: a human rejects; no money moves.
- `GET  /api/cash`: current checking balance from `cash_accounts`, plus open invoices, rent due, and cash left after all obligations.
- `POST /api/reset`: restore `data/campus_customs_new.db` from the original `data/campus_customs.db` for a fresh run (the audit trail is kept).

**Human-only MCP tools added for these routes:** `list_tickets` (tickets), `human_resolve_ticket` (tickets; Problem 8), `human_decide_approval` (approval_requests, payments, cash_accounts, invoices, leases, tickets), `human_reset_database` (copies the whole DB file). None of them is in any agent's allowlist. Approving: invoice → `invoices.status = 'paid'`; rent → `leases.next_due` + 1 month; restock → a `payments` row (kind `restock`, stock changes on delivery, not on approval). A ticket is resolved when its run finishes (and, as a fallback, once a human has decided all of its requests).

**Verified live (HTTP against :8000):** reset → $3,400; ran ticket 102 (boss → facilities, 8 model calls; `/api/events` showed 12 events mid-run; a second run got 409); approved request 1 → payment row signed "Gaurang", checking $3,400 → $1,000, lease due → 2026-10-02, ticket 102 resolved; re-approve → 409; no approver → 422; unknown id → 404; reset again → fresh.

---

## 7. Dashboard (`frontend/`)
`frontend/` (React + Vite + TypeScript). Start with `npm run dev` in `frontend/`; it opens **http://localhost:5173** and calls the backend at **http://localhost:8000** (`frontend/.env`). The backend CORS allows `http://localhost:5173` explicitly (plus other localhost ports).

| Requirement | Where on the board |
|---|---|
| List all three tickets | **Mission Board** holocards (left), with status pills + pending-approval counts |
| Pick a ticket and start the team | Click a holocard → **Dispatch the Council** → `POST /api/tickets/{id}/run` |
| Each agent and what it's saying/doing during the run | **Council seats** (live status + current tool call) and **Transmissions** feed (polls `/api/events` every 1.2 s) |
| Mark a ticket resolved when the run finishes | RESOLVED stamp on the holocard + board progress bar (backend resolves it on run success) |
| Short summary of what each agent did | **Council Debrief** (one card per agent: summary, actions, tools; "Not called: …") |
| Human approves a payment/purchase | **Awaiting Your Seal** cards → optional note → Approve & pay / Reject (desk officer name required; Approve disabled if it would overdraw) |
| Checking balance drops after approval | **Treasury Vault**: animated count-down, −$ flash, gauge with $500 floor, ledger |

Design rationale: `output/design.md`.
Screenshots of the board after each resolved ticket: `output/resolved_board.html`.

---

## 8. Safety & guardrails

### Real customers & real money
1. **Agents propose, humans dispose.** No MCP tool can pay, discount, order stock or send a message. Agents can only `submit_approval_request`. `payments.approved_by` is NOT NULL, so even the schema demands a named human.
2. **Server-side validation, not just prompt rules.** `submit_approval_request` rejects payment amounts that don't exactly match the invoice/lease, payments on already-paid invoices, unknown ids, discounts below `unit_cost` or not below list, and customer replies with no text.
3. **Least-privilege tool access.** Each agent sees only its own MCP tools (`AgentSpec.mcp_tools`, enforced by `MCPToolset.filtered` *and* re-checked in `process_tool_call`).
4. **Approval rights per role.** inventory → `restock_order`, accounting → `pay_invoice` / `price_override`, facilities → `pay_rent`, customer_service → `customer_reply`, boss → none. Enforced in code (`Team._guard_mcp_call`).
5. **No impersonation.** `requested_by` / `agent` are overwritten with the real calling agent before the MCP call.
6. **Agents never resolve tickets.** Agents may set `in_progress`, `waiting_on_stock` or `awaiting_approval`; `resolved` is rejected. Since Problem 8 the *backend* marks a ticket resolved when a run that a human started from the dashboard finishes (`human_resolve_ticket`); any approvals it produced stay pending until a human decides them.
7. **No duplicates.** One pending approval per ticket + kind, so reruns can't stack payments.
8. **No invented facts.** Prompts require every number to come from a tool, reports tag each fact with its source tool, and tools return `found: false` instead of guessing.
9. **Cash floor ($500).** Accounting, facilities and the boss must flag any set of payments that would leave checking under $500 and leave the order of payment to the human.
10. **Phishing/notice verification.** Landlord or vendor emails are treated as claims. Facilities checks the amount, payee and date against `leases`; a different payee, new bank details or an "urgent wire" is reported, never paid.
11. **Customer privacy.** Customer replies never mention costs, margins, vendors, invoices, rent, cash or other customers. Dates are "estimated" and discounts "pending approval."
12. **Full audit trail.** `output/audit_trail.json` is **append-only** (atomic write; a corrupt file is moved aside, never wiped). It records every step of every agent loop: prompt, model decision (text + tool calls + args), tool results, delegations (including refused/reused ones), the final report, errors, and token usage. Entries are linked by `team_run_id` / `run_id` / `chain`.
13. **Named human on every decision.** The dashboard won't approve or reject without a desk officer name. It's stored as `approval_requests.decided_by` and `payments.approved_by`, along with an optional note.
14. **No overdrafts.** The board disables Approve when "checking after" would go negative, and `human_decide_approval` refuses anyway. Seen in Problem 9: the $264 restock against $160.
15. **Secrets.** The Portkey key lives only in `HW5/.env` (chmod 600, git-ignored), never in code, prompts or the audit trail.

### Token & loop limits (`backend/config.py`)
| Limit | Value | Why |
|---|---|---|
| Model calls per ticket (whole team, shared counter) | 30 | Hard stop on runaway loops (`UsageLimits.request_limit`) |
| Tool calls per ticket (whole team) | 45 | `UsageLimits.tool_calls_limit` |
| Total tokens per ticket (whole team) | 150k | `UsageLimits.total_tokens_limit` |
| Output tokens per model response | 1,500 | `max_tokens` |
| Delegation depth | 3 (boss → A → B → C) | Prevents deep chains |
| Delegations per run | boss 3, specialist 1 | The boss routes; specialists rarely need to |
| No loop-backs | can't delegate to self or anyone already in the chain | Stops A → B → A ping-pong |
| Report reuse | asking an agent that already reported in this team run returns its report | Never pay twice for the same work |
| Audit text clip | 3,000 chars per tool result / text | Keeps the trail readable and small |
| Prompt rules | "facts first, then customer_service with the facts pasted in"; one call per tool per args | Cut ticket 103 from 28 calls / 71k input tokens to 15 / 41k |

---

## 9. Plan vs actual, and the final run (Problems 6 + 9)
Full write-up: `output/desk_tickets.html` (one tab per ticket with **Expected** next to **Actual**, plus the **Cash** tab).

### Expected (Problem 6)

| Ticket | Boss calls first | Expected delegations | Not called | Expected approvals |
|---|---|---|---|---|
| 101 tee order | inventory: "do we have the shirt?" decides everything, and invoice 501 may already be the restock | boss → inventory → accounting → customer_service (3) | facilities | pay_invoice $840, customer_reply |
| 102 rent | facilities: owns the lease and must verify the email against it | boss → facilities (1) | inventory, accounting, customer_service | pay_rent $2,400 |
| 103 bulk hoodies | inventory: no point pricing 20 units until we know only 8 exist | boss → inventory → accounting → customer_service (3) | facilities | restock_order 12 × $22 = $264, price_override 20 × $49.30 = $986, customer_reply |

No specialist-to-specialist delegations are expected on any ticket. The boss passes facts forward instead.

### Actual: full run on the board (Problem 9, 2026-10-11, working DB reset first)
| Ticket | Boss called first | Actual delegations | Not called | Approvals filed → human decision (Gaurang) | Calls / tokens |
|---|---|---|---|---|---|
| 101 | inventory **+** accounting in the same turn | boss ⇉ inventory, accounting → customer_service (3) | facilities ✓ | #1 pay_invoice $840 → **approved**; #2 customer_reply → **approved** | 14 / 40,017 |
| 102 | facilities ✓ | boss → facilities (1) ✓ | inventory, accounting, customer_service ✓ | #3 pay_rent $2,400 → **approved** | 8 / 20,665 |
| 103 | inventory **+** accounting in the same turn | boss ⇉ inventory, accounting → customer_service (3) | facilities ✓ | #4 price_override 20 × $49.30 = $986 → **approved**; #5 restock 12 × $22 = $264 → **rejected** (only $160 left); #6 customer_reply → **rejected** (redraft) | 15 / 42,838 |

**What matched:** every ticket reached exactly the planned specialists, with 3 / 1 / 3 delegations and no specialist-to-specialist hops, refusals or re-runs. Every expected approval was filed, every should-not-appear tool stayed unused, and no duplicate restock was filed for 101.
**What differed:** on 101 and 103 the boss sent inventory and accounting in parallel instead of one after the other. On 103 accounting skipped its own `get_cash_position` (the boss covered it). Specialists made a few extra lookups (`get_ticket`, `get_shop_date`, `list_approval_requests`).

### Cash (reconciled with `cash_accounts`)
| Step | Change | Checking |
|---|---|---|
| Start (after reset) | n/a | **$3,400.00** |
| 101 resolved: approved #1, invoice 501 to Bulldog Print Co (payment #1) | −$840.00 | $2,560.00 |
| 102 resolved: approved #3, September rent, lease 1 (payment #2) | −$2,400.00 | $160.00 |
| 103 resolved: restock #5 rejected (would overdraw); discount #4 approved but non-cash | $0.00 | $160.00 |
| **End** | **−$3,240.00** | **$160.00** = `cash_accounts.balance` ✓ |

Machine-readable outcome per ticket: `output/resolved_tickets.json` (asserts that the cash reconciles before writing).

### Earlier: first team run (Problem 5, CLI, before the dashboard existed)
| Ticket | Agents that ran | Approvals filed | Model calls / input tokens |
|---|---|---|---|
| 101 | boss → inventory, accounting, customer_service | #1 pay_invoice $840, #2 customer_reply | 14 / 36.6k |
| 102 | boss → facilities | #3 pay_rent $2,400 | 8 / 20.1k |
| 103 | boss → inventory, accounting, customer_service | #4 price_override 20 × $49.30 = $986, #5 restock 12 from vendor 1 = $264, #6 customer_reply | 15 / 40.9k |

All three tickets were set to `awaiting_approval`. Every report flags that paying invoice 501 plus rent leaves **$160, under the $500 cash floor**, and leaves the decision to the human.

---

## 10. Files
| Path | What |
|---|---|
| `data/campus_customs.db` / `data/campus_customs_new.db` | original (never written) / working copy |
| `mcp_server/` | `server.py` (FastMCP, 16 tools), `db.py` (SQL), `smoke_test.py`, `README.md` |
| `.mcp.json` | MCP connection config (also used by the backend) |
| `backend/` | `main.py` (FastAPI), `team.py` (agent runtime), `agents/*.py` (5 role specs), `prompts/*.md` (5 prompts), `models.py`, `audit.py`, `config.py`, `run_team.py` (CLI) |
| `frontend/` | React + Vite + TS desk (`src/components/*`, `src/api.ts`, `src/derive.ts`, `src/index.css`) |
| `output/harness.md` | this file |
| `output/mcp_smoke.json` | Problem 4 MCP smoke test evidence |
| `output/audit_trail.json` | append-only log of every agent-loop step |
| `output/desk_tickets.html` | expected vs actual per ticket, Cash tab (reconciled) and Reflection tab |
| `output/design.md` | dashboard design rationale |
| `output/resolved_tickets.json` | final outcome per ticket, agent contributions, human approvals, cash |
| `output/resolved_board.html` | screenshots of the board for each resolved ticket |
| `AI_prompts.md` | log of my prompts, per problem |
