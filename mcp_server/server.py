"""Campus Customs MCP server.

Shared tool belt for every agent (Boss, Inventory, Accounting, Facilities,
Customer Service). Talks to data/campus_customs_new.db via db.py.

Run:  .venv/bin/python mcp_server/server.py   (stdio; the backend starts it for you)
"""

try:
    from fastmcp import FastMCP  # standalone FastMCP (same venv as the backend)
except ImportError:  # fall back to the FastMCP bundled in the official mcp<2 SDK
    from mcp.server.fastmcp import FastMCP

import db

mcp = FastMCP("campus-customs")


@mcp.tool()
def check_stock(sku: str, size: str) -> dict:
    """Look up how many units of one SKU in one size are on hand, and where.

    Also returns every other size of the same SKU so an agent can offer an
    alternative when the requested size is out of stock.
    Example: check_stock("CC-TEE-WHITE", "S")
    """
    return db.check_stock(sku, size)


@mcp.tool()
def get_lease_rent_status(lease_id: int) -> dict:
    """Get the rent amount and due date for a lease, how many days until it is
    due (measured from the shop's desk date), and whether cash on hand covers it.

    Example: get_lease_rent_status(1)
    """
    return db.get_lease_rent_status(lease_id)


@mcp.tool()
def quote_bulk_order(sku: str, size: str, qty: int) -> dict:
    """Price a bulk request: total at list price, unit cost (the lowest price
    that does not lose money), margin, and how many units we are short.

    This tool only reports numbers; it never approves or applies a discount.
    Example: quote_bulk_order("CC-HOOD-NAVY", "M", 20)
    """
    return db.quote_bulk_order(sku, size, qty)


# --- Problem 5: tools the agent team needs to work the open tickets -----------


@mcp.tool()
def get_shop_date() -> dict:
    """The shop's business date (desk.date_today). Use this as 'today' for all
    due-date and overdue math; never use the system clock."""
    return db.get_shop_date()


@mcp.tool()
def list_open_tickets() -> dict:
    """Every ticket a human has not resolved yet: id, type, requester, subject, status."""
    return db.list_open_tickets()


@mcp.tool()
def get_ticket(ticket_id: int) -> dict:
    """Full ticket row (request details, notes, status) plus the ids of the
    records it links to (sku/size, invoice_id, lease_id)."""
    return db.get_ticket(ticket_id)


@mcp.tool()
def get_invoice(invoice_id: int) -> dict:
    """A vendor invoice with its vendor's name, specialty and lead days, how
    many days overdue it is (from the shop date), and what has been paid."""
    return db.get_invoice(invoice_id)


@mcp.tool()
def list_vendors() -> dict:
    """All vendors with id, specialty and lead_days (days to deliver)."""
    return db.list_vendors()


@mcp.tool()
def get_cash_position() -> dict:
    """Cash on hand vs. ALL open invoices and rent due in the next 30 days,
    with what would be left after paying everything."""
    return db.get_cash_position()


@mcp.tool()
def list_approval_requests(status: str = "pending") -> dict:
    """Proposals waiting for (or decided by) a human. status: pending,
    approved, rejected, or all."""
    return db.list_approval_requests(status)


@mcp.tool()
def update_ticket_status(ticket_id: int, status: str, note: str, agent: str) -> dict:
    """Move a ticket to in_progress, waiting_on_stock or awaiting_approval and
    append a timestamped note signed by the agent. Agents cannot resolve tickets."""
    return db.update_ticket_status(ticket_id, status, note, agent)


@mcp.tool()
def submit_approval_request(
    ticket_id: int,
    kind: str,
    summary: str,
    requested_by: str,
    ref_id: int | None = None,
    amount: float | None = None,
    unit_price: float | None = None,
    qty: int | None = None,
    vendor_id: int | None = None,
    message: str | None = None,
) -> dict:
    """Queue a proposal for a human to approve on the dashboard. Nothing is
    paid, discounted, ordered or sent until a human approves it.

    kind and required fields:
      pay_invoice    ref_id=invoice id, amount = exact invoice amount
      pay_rent       ref_id=lease id,   amount = exact monthly_rent
      price_override unit_price (>= unit_cost, < list_price), qty
      restock_order  qty, vendor_id   (cost is computed from pricing.unit_cost)
      customer_reply message = the draft text to send the requester
    Rejects any number that does not match the database. One pending request
    per ticket + kind; duplicates return the existing id.
    """
    return db.submit_approval_request(
        ticket_id, kind, summary, requested_by, ref_id, amount, unit_price, qty, vendor_id, message
    )


# --- Problem 7: dashboard / human-only tools ------------------------------------
# Not in any agent's allowlist (backend/agents/*.py); the team runtime also
# blocks them in process_tool_call. Only the FastAPI backend calls these, and
# only in response to a human clicking on the dashboard.


@mcp.tool()
def list_tickets() -> dict:
    """All tickets, open and resolved, with pending-approval counts (dashboard)."""
    return db.list_tickets()


@mcp.tool()
def human_decide_approval(approval_id: int, decision: str, approver: str, note: str = "") -> dict:
    """HUMAN ONLY. Approve or reject an approval request. Approving pay_invoice,
    pay_rent or restock_order writes a `payments` row (approved_by = approver)
    and lowers the checking balance. Refuses to overdraw."""
    return db.human_decide_approval(approval_id, decision, approver, note)


@mcp.tool()
def human_reset_database() -> dict:
    """HUMAN ONLY. Overwrite data/campus_customs_new.db with the original data."""
    return db.human_reset_database()



@mcp.tool()
def human_resolve_ticket(ticket_id: int, resolved_by: str, note: str = "") -> dict:
    """SYSTEM/HUMAN ONLY. Mark a ticket resolved after the team run a human started
    has finished. Pending approvals stay in the queue for the human."""
    return db.human_resolve_ticket(ticket_id, resolved_by, note)

if __name__ == "__main__":
    db.ensure_schema()
    mcp.run()
