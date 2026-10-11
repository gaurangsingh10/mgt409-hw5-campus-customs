"""Database queries behind the Campus Customs MCP tools.

Every function reads data/campus_customs_new.db (the working copy) and returns
only what is in the database, plus simple arithmetic on those values. If a row
is missing, the function says so instead of guessing.
"""

import os
import shutil
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB", DEFAULT_DB_PATH))


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    # Read-only connection for lookups; writes go through _connect_rw().
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _today(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return row["date_today"]


def check_stock(sku: str, size: str) -> dict:
    """Stock for one SKU + size, plus every other size of that SKU."""
    sku, size = sku.strip().upper(), size.strip().upper()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid",
            (sku,),
        ).fetchall()
    if not rows:
        return {"found": False, "error": f"No inventory rows for SKU '{sku}'."}

    requested = next((dict(r) for r in rows if r["size"] == size), None)
    if requested is None:
        return {
            "found": False,
            "error": f"SKU '{sku}' has no size '{size}'.",
            "sizes_on_file": [r["size"] for r in rows],
        }

    return {
        "found": True,
        "sku": sku,
        "name": requested["name"],
        "size": size,
        "qty_on_hand": requested["qty"],
        "in_stock": requested["qty"] > 0,
        "location": requested["location"],
        "all_sizes": [{"size": r["size"], "qty": r["qty"]} for r in rows],
    }


def get_lease_rent_status(lease_id: int) -> dict:
    """Rent amount, due date, days until due (from desk.date_today), and cash on hand."""
    with _connect() as conn:
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"found": False, "error": f"No lease with id {lease_id}."}
        today = _today(conn)
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()

    days_until_due = (date.fromisoformat(lease["next_due"]) - date.fromisoformat(today)).days
    total_cash = sum(a["balance"] for a in accounts)
    return {
        "found": True,
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "shop_today": today,
        "days_until_due": days_until_due,
        "overdue": days_until_due < 0,
        "notes": lease["notes"],
        "cash_accounts": [dict(a) for a in accounts],
        "total_cash": total_cash,
        "cash_after_rent": total_cash - lease["monthly_rent"],
        "can_cover_rent": total_cash >= lease["monthly_rent"],
    }


def quote_bulk_order(sku: str, size: str, qty: int) -> dict:
    """List-price total, cost floor, margin, and stock shortfall for a bulk request."""
    sku, size = sku.strip().upper(), size.strip().upper()
    if qty <= 0:
        return {"found": False, "error": "qty must be a positive integer."}
    with _connect() as conn:
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        stock = conn.execute(
            "SELECT name, qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
    if price is None:
        return {"found": False, "error": f"No pricing row for SKU '{sku}'."}
    if stock is None:
        return {"found": False, "error": f"No inventory row for SKU '{sku}' size '{size}'."}

    unit_cost, list_price = price["unit_cost"], price["list_price"]
    return {
        "found": True,
        "sku": sku,
        "name": stock["name"],
        "size": size,
        "qty_requested": qty,
        "qty_on_hand": stock["qty"],
        "shortfall": max(0, qty - stock["qty"]),
        "list_price": list_price,
        "unit_cost": unit_cost,
        "unit_margin_at_list": round(list_price - unit_cost, 2),
        "total_at_list": round(list_price * qty, 2),
        "total_cost": round(unit_cost * qty, 2),
        # Any discounted price below unit_cost loses money on every unit.
        "price_floor_per_unit": unit_cost,
        "max_discount_pct_before_loss": round((1 - unit_cost / list_price) * 100, 1),
    }


# ---------------------------------------------------------------------------
# Problem 5 tools: ticket queue, invoices, vendors, cash, approvals.
# ---------------------------------------------------------------------------


# Statuses an agent may set. "resolved" is deliberately missing: only a human
# closes a ticket (from the dashboard).
AGENT_TICKET_STATUSES = ("in_progress", "waiting_on_stock", "awaiting_approval")
APPROVAL_KINDS = ("pay_invoice", "pay_rent", "price_override", "restock_order", "customer_reply")


def _connect_rw() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema() -> None:
    """Create the approval queue table in the working copy if it's missing.

    This is a queue for agent proposals; it holds no shop facts of its own.
    """
    with _connect_rw() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS approval_requests (
                id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                ref_id INTEGER,
                amount REAL,
                unit_price REAL,
                qty INTEGER,
                vendor_id INTEGER,
                message TEXT,
                summary TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                decided_by TEXT,
                decided_at TEXT,
                decision_note TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )"""
        )


def get_shop_date() -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
    return {"shop_today": row["date_today"], "desk_notes": row["notes"]}


def list_open_tickets() -> dict:
    """Every ticket that a human has not resolved yet."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, status, created_at FROM tickets "
            "WHERE status != 'resolved' ORDER BY created_at"
        ).fetchall()
    return {"count": len(rows), "tickets": [dict(r) for r in rows]}


def get_ticket(ticket_id: int) -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return {"found": False, "error": f"No ticket with id {ticket_id}."}
    ticket = dict(row)
    # Point agents at the linked records (by FK) without guessing anything.
    linked = {}
    if ticket["sku"]:
        linked["inventory"] = {"sku": ticket["sku"], "size": ticket["size"], "qty_requested": ticket["qty"]}
    if ticket["invoice_id"] is not None:
        linked["invoice_id"] = ticket["invoice_id"]
    if ticket["lease_id"] is not None:
        linked["lease_id"] = ticket["lease_id"]
    return {"found": True, "ticket": ticket, "linked_records": linked}


def get_invoice(invoice_id: int) -> dict:
    """An invoice with its vendor, and days overdue measured from the desk date."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT i.id, i.vendor_id, i.amount, i.due_date, i.status, i.description, "
            "v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days AS vendor_lead_days "
            "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (invoice_id,),
        ).fetchone()
        if row is None:
            return {"found": False, "error": f"No invoice with id {invoice_id}."}
        today = _today(conn)
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE kind = 'invoice' AND ref_id = ?",
            (invoice_id,),
        ).fetchone()["total"]
    days_past_due = (date.fromisoformat(today) - date.fromisoformat(row["due_date"])).days
    return {
        "found": True,
        **dict(row),
        "shop_today": today,
        "days_overdue": max(0, days_past_due),
        "overdue": row["status"] != "paid" and days_past_due > 0,
        "amount_paid_so_far": paid,
        "balance_due": row["amount"] - paid,
    }


def list_vendors() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id").fetchall()
    return {"vendors": [dict(r) for r in rows]}


def get_cash_position() -> dict:
    """Cash on hand vs. every open invoice and every lease due in the next 30 days."""
    with _connect() as conn:
        today = _today(conn)
        accounts = [dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts")]
        invoices = [
            dict(r)
            for r in conn.execute(
                "SELECT i.id, v.name AS vendor_name, i.amount, i.due_date, i.description "
                "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.status != 'paid' ORDER BY i.due_date"
            )
        ]
        leases = [
            dict(r)
            for r in conn.execute("SELECT id, space_name, landlord, monthly_rent, next_due FROM leases ORDER BY next_due")
        ]
    today_d = date.fromisoformat(today)
    rent_due_soon = [l for l in leases if (date.fromisoformat(l["next_due"]) - today_d).days <= 30]
    total_cash = sum(a["balance"] for a in accounts)
    owed_invoices = sum(i["amount"] for i in invoices)
    owed_rent = sum(l["monthly_rent"] for l in rent_due_soon)
    return {
        "shop_today": today,
        "cash_accounts": accounts,
        "total_cash": total_cash,
        "open_invoices": invoices,
        "open_invoices_total": owed_invoices,
        "rent_due_next_30_days": rent_due_soon,
        "rent_due_total": owed_rent,
        "cash_after_all_obligations": total_cash - owed_invoices - owed_rent,
    }


def list_approval_requests(status: str = "pending") -> dict:
    ensure_schema()
    with _connect() as conn:
        if status == "all":
            rows = conn.execute("SELECT * FROM approval_requests ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM approval_requests WHERE status = ? ORDER BY id", (status,)).fetchall()
    return {"count": len(rows), "requests": [dict(r) for r in rows]}


def update_ticket_status(ticket_id: int, status: str, note: str, agent: str) -> dict:
    if status not in AGENT_TICKET_STATUSES:
        return {"ok": False, "error": f"Agents may only set status to one of {list(AGENT_TICKET_STATUSES)}. "
                                      "Only a human can resolve a ticket."}
    with _connect_rw() as conn:
        row = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        if row["status"] == "resolved":
            return {"ok": False, "error": f"Ticket {ticket_id} is already resolved by a human."}
        new_notes = f"{row['notes'] or ''}\n[{agent} @ {_now()}] {note}".strip()
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, new_notes, ticket_id))
    return {"ok": True, "ticket_id": ticket_id, "old_status": row["status"], "new_status": status}


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
    """Queue a proposal for a human. Validates every number against the database."""
    if kind not in APPROVAL_KINDS:
        return {"ok": False, "error": f"kind must be one of {list(APPROVAL_KINDS)}."}
    ensure_schema()
    with _connect_rw() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}

        # --- validate against the database: agents cannot propose made-up numbers ---
        if kind == "pay_invoice":
            inv = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if inv is None:
                return {"ok": False, "error": f"pay_invoice needs ref_id = a real invoice id; {ref_id} not found."}
            if inv["status"] == "paid":
                return {"ok": False, "error": f"Invoice {ref_id} is already paid."}
            if amount is None or abs(amount - inv["amount"]) > 0.005:
                return {"ok": False, "error": f"amount must equal invoice {ref_id}'s amount ({inv['amount']})."}
        elif kind == "pay_rent":
            lease = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return {"ok": False, "error": f"pay_rent needs ref_id = a real lease id; {ref_id} not found."}
            if amount is None or abs(amount - lease["monthly_rent"]) > 0.005:
                return {"ok": False, "error": f"amount must equal lease {ref_id}'s monthly_rent ({lease['monthly_rent']})."}
        elif kind == "price_override":
            if not ticket["sku"] or unit_price is None or not qty:
                return {"ok": False, "error": "price_override needs a ticket with a sku, plus unit_price and qty."}
            price = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],)).fetchone()
            if unit_price < price["unit_cost"]:
                return {"ok": False, "error": f"unit_price {unit_price} is below unit_cost {price['unit_cost']}; never sell at a loss."}
            if unit_price >= price["list_price"]:
                return {"ok": False, "error": f"unit_price {unit_price} is not a discount off list {price['list_price']}."}
            amount = round(unit_price * qty, 2)
        elif kind == "restock_order":
            if not ticket["sku"] or not qty or vendor_id is None:
                return {"ok": False, "error": "restock_order needs a ticket with a sku, plus qty and vendor_id."}
            if conn.execute("SELECT 1 FROM vendors WHERE id = ?", (vendor_id,)).fetchone() is None:
                return {"ok": False, "error": f"No vendor with id {vendor_id}."}
            cost = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (ticket["sku"],)).fetchone()
            amount = round(cost["unit_cost"] * qty, 2)  # estimated cost from pricing.unit_cost
        elif kind == "customer_reply":
            if not message or not message.strip():
                return {"ok": False, "error": "customer_reply needs the draft message text."}

        # --- one pending request per ticket + kind, so reruns don't pile up duplicates ---
        dup = conn.execute(
            "SELECT id FROM approval_requests WHERE ticket_id = ? AND kind = ? AND status = 'pending'",
            (ticket_id, kind),
        ).fetchone()
        if dup:
            return {"ok": True, "duplicate": True, "approval_id": dup["id"],
                    "note": "A pending request of this kind already exists for this ticket; nothing new was created."}

        cur = conn.execute(
            "INSERT INTO approval_requests (ticket_id, kind, ref_id, amount, unit_price, qty, vendor_id, "
            "message, summary, requested_by, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?, 'pending', ?)",
            (ticket_id, kind, ref_id, amount, unit_price, qty, vendor_id, message, summary, requested_by, _now()),
        )
    return {"ok": True, "duplicate": False, "approval_id": cur.lastrowid, "kind": kind,
            "amount": amount, "status": "pending", "note": "Waiting for a human on the dashboard."}


# ---------------------------------------------------------------------------
# Problem 7: dashboard / human-only tools. These are NOT in any agent's
# allowlist; only the FastAPI backend calls them, after a human clicks.
# ---------------------------------------------------------------------------


ORIGINAL_DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_ORIGINAL_DB", DB_PATH.parent / "campus_customs.db"))
CASH_FLOOR = 500.0
CASH_ACCOUNT = "checking"


def _add_one_month(iso_day: str) -> str:
    d = date.fromisoformat(iso_day)
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):  # clamp e.g. Jan 31 -> Feb 28
        try:
            return date(y, m, day).isoformat()
        except ValueError:
            continue
    raise ValueError(iso_day)


def list_tickets() -> dict:
    """All tickets (open and resolved) with their pending-approval counts."""
    ensure_schema()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT t.id, t.type, t.requester, t.subject, t.sku, t.size, t.qty, t.lease_id, t.invoice_id, "
            "t.status, t.notes, t.created_at, "
            "(SELECT COUNT(*) FROM approval_requests a WHERE a.ticket_id = t.id AND a.status = 'pending') AS pending_approvals "
            "FROM tickets t ORDER BY t.id"
        ).fetchall()
    return {"tickets": [{**dict(r), "state": "resolved" if r["status"] == "resolved" else "open"} for r in rows]}


def human_decide_approval(approval_id: int, decision: str, approver: str, note: str = "") -> dict:
    """Apply a human's decision. Approving a pay_invoice / pay_rent / restock_order is
    the ONLY path that writes `payments` and changes `cash_accounts`."""
    if decision not in ("approved", "rejected"):
        return {"ok": False, "error": "decision must be 'approved' or 'rejected'."}
    if not approver or not approver.strip():
        return {"ok": False, "error": "approver (a human's name) is required."}
    approver = approver.strip()
    ensure_schema()
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")  # one transaction: payment + cash + status all or nothing
        req = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (approval_id,)).fetchone()
        if req is None:
            conn.rollback()
            return {"ok": False, "error": f"No approval request {approval_id}."}
        if req["status"] != "pending":
            conn.rollback()
            return {"ok": False, "error": f"Request {approval_id} was already {req['status']} by {req['decided_by']}."}

        today = _today(conn)
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()
        cash_before = cash["balance"]
        result = {"ok": True, "approval_id": approval_id, "kind": req["kind"], "decision": decision,
                  "cash_before": cash_before, "cash_after": cash_before, "payment_id": None, "warnings": []}

        if decision == "approved" and req["kind"] in ("pay_invoice", "pay_rent", "restock_order"):
            amount = req["amount"]
            if req["kind"] == "pay_invoice":
                inv = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
                if inv is None or inv["status"] == "paid":
                    conn.rollback()
                    return {"ok": False, "error": f"Invoice {req['ref_id']} is missing or already paid."}
                amount = inv["amount"]  # pay what the invoice says, re-read at decision time
            elif req["kind"] == "pay_rent":
                lease = conn.execute("SELECT monthly_rent, next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
                if lease is None:
                    conn.rollback()
                    return {"ok": False, "error": f"Lease {req['ref_id']} not found."}
                amount = lease["monthly_rent"]
            if amount > cash_before:
                conn.rollback()
                return {"ok": False, "error": f"Not enough cash: ${amount:,.2f} needed, ${cash_before:,.2f} in {CASH_ACCOUNT}. "
                                              "Nothing was paid."}

            kind_map = {"pay_invoice": "invoice", "pay_rent": "rent", "restock_order": "restock"}
            # ref_id: invoice id / lease id, or the approval id for a restock purchase
            ref = req["ref_id"] if req["kind"] != "restock_order" else approval_id
            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
                (kind_map[req["kind"]], ref, amount, CASH_ACCOUNT, _now(), approver),
            )
            cash_after = round(cash_before - amount, 2)
            conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (cash_after, today, CASH_ACCOUNT))
            if req["kind"] == "pay_invoice":
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            elif req["kind"] == "pay_rent":
                new_due = _add_one_month(lease["next_due"])
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, req["ref_id"]))
                result["lease_next_due"] = new_due
            result.update(payment_id=cur.lastrowid, amount_paid=amount, cash_after=cash_after)
            if cash_after < CASH_FLOOR:
                result["warnings"].append(f"Checking is now ${cash_after:,.2f}, below the ${CASH_FLOOR:,.0f} cash floor.")

        conn.execute(
            "UPDATE approval_requests SET status = ?, decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (decision, approver, _now(), note or None, approval_id),
        )
        # When a human has decided every request on a ticket, the ticket is resolved.
        left = conn.execute(
            "SELECT COUNT(*) FROM approval_requests WHERE ticket_id = ? AND status = 'pending'", (req["ticket_id"],)
        ).fetchone()[0]
        t = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (req["ticket_id"],)).fetchone()
        line = f"[human:{approver} @ {_now()}] {decision} request {approval_id} ({req['kind']})" + (f": {note}" if note else "")
        new_status = "resolved" if left == 0 else t["status"]
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
                     (new_status, f"{t['notes'] or ''}\n{line}".strip(), req["ticket_id"]))
        conn.commit()
        result.update(ticket_id=req["ticket_id"], ticket_status=new_status, pending_left_on_ticket=left)
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def human_reset_database() -> dict:
    """Overwrite the working copy with the original data (for a fresh run)."""
    if ORIGINAL_DB_PATH.resolve() == DB_PATH.resolve():
        return {"ok": False, "error": "Refusing to reset: the working DB *is* the original."}
    if not ORIGINAL_DB_PATH.exists():
        return {"ok": False, "error": f"Original DB not found at {ORIGINAL_DB_PATH}."}
    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    ensure_schema()
    with _connect() as conn:
        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()[0]
        open_tickets = conn.execute("SELECT COUNT(*) FROM tickets WHERE status != 'resolved'").fetchone()[0]
    return {"ok": True, "reset_from": ORIGINAL_DB_PATH.name, "working_copy": DB_PATH.name,
            "checking_balance": balance, "open_tickets": open_tickets, "approval_requests": 0}


def human_resolve_ticket(ticket_id: int, resolved_by: str, note: str = "") -> dict:
    """Mark a ticket resolved (system/human only). Pending approvals stay in the queue."""
    with _connect_rw() as conn:
        t = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        if t["status"] == "resolved":
            return {"ok": True, "ticket_id": ticket_id, "status": "resolved", "already": True}
        line = f"[{resolved_by} @ {_now()}] resolved" + (f": {note}" if note else "")
        conn.execute("UPDATE tickets SET status = 'resolved', notes = ? WHERE id = ?",
                     (f"{t['notes'] or ''}\n{line}".strip(), ticket_id))
    return {"ok": True, "ticket_id": ticket_id, "old_status": t["status"], "status": "resolved"}
