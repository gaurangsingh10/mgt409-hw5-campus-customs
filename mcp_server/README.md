# Campus Customs MCP Server

## What it's for
This is the shared tool belt for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents never run SQL themselves. Every shop fact they use comes from these tools, straight from the database. If a ticket, SKU, size, invoice or lease doesn't exist, the tool returns `{"found": false, "error": ...}` instead of making something up.

## Database
- **File:** `data/campus_customs_new.db` (the working copy; the original `data/campus_customs.db` is never touched)
- Override with the `CAMPUS_CUSTOMS_DB` environment variable if needed.
- Lookups open the DB **read-only**. Only the two write tools below change anything.
- On startup the server creates an `approval_requests` table (a queue of agent proposals for the human) in the working copy if it's missing.

## Tools (15: 12 for agents + 3 dashboard/human-only)
| Tool | Tables | R/W | What it's for |
|---|---|---|---|
| `check_stock(sku, size)` | `inventory` | R | Units on hand for one size + every other size (ticket 101) |
| `get_lease_rent_status(lease_id)` | `leases`, `desk`, `cash_accounts` | R | Rent, due date, days until due, can cash cover it (ticket 102) |
| `quote_bulk_order(sku, size, qty)` | `pricing`, `inventory` | R | List total, unit cost floor, margin, max discount, shortfall (ticket 103) |
| `get_shop_date()` | `desk` | R | The shop's "today" for all due/overdue math |
| `list_open_tickets()` | `tickets` | R | Every ticket not yet resolved by a human |
| `get_ticket(ticket_id)` | `tickets` | R | Full ticket + linked sku/size, invoice_id, lease_id |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `payments`, `desk` | R | Invoice + vendor, days overdue, balance due |
| `list_vendors()` | `vendors` | R | Vendors, specialties, lead days |
| `get_cash_position()` | `cash_accounts`, `invoices`, `vendors`, `leases`, `desk` | R | Cash vs. all open invoices + rent due in 30 days |
| `list_approval_requests(status)` | `approval_requests` | R | Pending / approved / rejected / all proposals |
| `update_ticket_status(ticket_id, status, note, agent)` | `tickets` | W | Set in_progress / waiting_on_stock / awaiting_approval + signed note (never resolved) |
| `submit_approval_request(...)` | `approval_requests` (validated against `invoices`, `leases`, `pricing`, `vendors`, `tickets`) | W | Propose pay_invoice, pay_rent, price_override, restock_order or customer_reply for human approval |
| `list_tickets()` *(dashboard)* | `tickets`, `approval_requests` | R | All tickets, open + resolved, with pending-approval counts |
| `human_decide_approval(approval_id, decision, approver, note)` *(human only)* | `approval_requests`, `payments`, `cash_accounts`, `invoices`, `leases`, `tickets` | W | Approve/reject a proposal; approving a payment/purchase is the only thing that moves cash |
| `human_reset_database()` *(human only)* | whole DB file | W | Restore the working copy from `data/campus_customs.db` |

**Safety:** The three dashboard/human-only tools are in no agent's allowlist; only `backend/main.py` calls them after a human clicks. No agent tool pays, discounts, orders stock or sends messages. `submit_approval_request` only *queues* a proposal and rejects amounts that don't match the database, prices below unit cost, unknown ids and duplicates. Payments, stock changes and approvals are human-only.

## Files
- `server.py`: FastMCP server that registers the tools
- `db.py`: the SQL queries (no MCP dependency, so they can be tested directly)
- `requirements.txt`: `fastmcp` only (the project-root `requirements.txt` installs everything, server + backend, in one venv)
- `smoke_test.py`: smoke test of the three ticket tools over MCP stdio, checked against SQLite (`--db`, `--out` options)

## Connecting
The server is registered as `campus-customs` in the project's `.mcp.json` with **relative** paths (`.venv/bin/python mcp_server/server.py`), so Claude Code / Cursor opened at the project root can use it, and the backend (`backend/team.py`) launches it from the same entry. It speaks MCP over **stdio**, so it runs as a child process of whoever connects to it.
```bash
# from the project root, after: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python mcp_server/server.py                                   # start it by hand (waits for a client on stdin)
.venv/bin/python mcp_server/smoke_test.py --db data/campus_customs.db --out /tmp/mcp_smoke.json   # check it
```
