"""MCP smoke test: connect to the server exactly as configured in HW5/.mcp.json,
call the three ticket tools over the MCP protocol (stdio), and cross-check every
value against the database with independent SQL.

    .venv/bin/python mcp_server/smoke_test.py                  # writes output/mcp_smoke.json
    .venv/bin/python mcp_server/smoke_test.py --db data/campus_customs.db --out /tmp/smoke.json

Note: run it on a freshly reset working copy (or --db data/campus_customs.db) to get
the Problem 4 numbers; after a full run, rent has been paid and lease 1 is due 2026-10-02.
"""

import argparse
import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

HW5 = Path(__file__).resolve().parent.parent
CONFIG = json.loads((HW5 / ".mcp.json").read_text())["mcpServers"]["campus-customs"]

CASES = [
    {
        "ticket": 101,
        "prompt": "Ticket 101: Tauhid Zaman wants a Classic Bulldog Tee (CC-TEE-WHITE) in size S. "
                  "Do we have one in stock, and what other sizes could we offer?",
        "tool": "check_stock",
        "arguments": {"sku": "CC-TEE-WHITE", "size": "S"},
    },
    {
        "ticket": 102,
        "prompt": "Ticket 102: Elm City Properties says rent is due in 2 days. "
                  "How much is rent on lease 1, when exactly is it due, and can our cash cover it?",
        "tool": "get_lease_rent_status",
        "arguments": {"lease_id": 1},
    },
    {
        "ticket": 103,
        "prompt": "Ticket 103: Yale AI Club wants 20 Basic Hoodies (CC-HOOD-NAVY) in size M with a bulk discount. "
                  "What would that cost at list, what's our floor, and do we have enough?",
        "tool": "quote_bulk_order",
        "arguments": {"sku": "CC-HOOD-NAVY", "size": "M", "qty": 20},
    },
]


def db_truth(db: Path, tool: str, args: dict) -> dict:
    """Values pulled straight from SQLite, independent of the server code."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = lambda sql, *p: conn.execute(sql, p).fetchone()
    if tool == "check_stock":
        qty, loc = q("SELECT qty, location FROM inventory WHERE sku=? AND size=?", args["sku"], args["size"])
        all_sizes = conn.execute("SELECT size, qty FROM inventory WHERE sku=? ORDER BY rowid", (args["sku"],)).fetchall()
        truth = {"qty_on_hand": qty, "location": loc, "all_sizes": [{"size": s, "qty": n} for s, n in all_sizes]}
    elif tool == "get_lease_rent_status":
        rent, due = q("SELECT monthly_rent, next_due FROM leases WHERE id=?", args["lease_id"])
        (today,) = q("SELECT date_today FROM desk")
        (cash,) = q("SELECT SUM(balance) FROM cash_accounts")
        truth = {"monthly_rent": rent, "next_due": due, "shop_today": today, "total_cash": cash}
    else:  # quote_bulk_order
        cost, price = q("SELECT unit_cost, list_price FROM pricing WHERE sku=?", args["sku"])
        (qty,) = q("SELECT qty FROM inventory WHERE sku=? AND size=?", args["sku"], args["size"])
        truth = {"unit_cost": cost, "list_price": price, "qty_on_hand": qty}
    conn.close()
    return truth


async def main(db: Path, out: Path) -> None:
    command = HW5 / CONFIG["command"]
    transport = StdioTransport(
        command=str(command),
        args=[str(HW5 / a) for a in CONFIG["args"]],
        env={"CAMPUS_CUSTOMS_DB": str(db)},
        cwd=str(HW5),
    )
    results = []
    async with Client(transport) as client:
        listed = [t.name for t in await client.list_tools()]
        for case in CASES:
            res = await client.call_tool(case["tool"], case["arguments"])
            output = res.data if isinstance(res.data, dict) else json.loads(res.content[0].text)
            truth = db_truth(db, case["tool"], case["arguments"])
            mismatches = {k: {"tool": output.get(k), "db": v} for k, v in truth.items() if output.get(k) != v}
            results.append({
                "ticket": case["ticket"], "prompt": case["prompt"], "tool": case["tool"],
                "arguments": case["arguments"], "tool_output": output,
                "db_check": {"values_read_directly_from_db": truth, "matches_db": not mismatches, "mismatches": mismatches},
            })

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "transport": "stdio (MCP protocol), launched from HW5/.mcp.json",
        "server": {"name": "campus-customs", "command": CONFIG["command"], "args": CONFIG["args"]},
        "database": str(db.relative_to(HW5)) if db.is_relative_to(HW5) else str(db),
        "tools_listed": listed,
        "all_passed": all(r["db_check"]["matches_db"] for r in results),
        "tests": results,
    }
    out.write_text(json.dumps(report, indent=2) + "\n")
    for r in results:
        print(f"{r['tool']:<24} ticket {r['ticket']}  matches_db={r['db_check']['matches_db']}")
    print(f"{len(listed)} tools listed · all_passed = {report['all_passed']} -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=HW5 / "data" / "campus_customs_new.db")
    ap.add_argument("--out", type=Path, default=HW5 / "output" / "mcp_smoke.json")
    a = ap.parse_args()
    asyncio.run(main(a.db.resolve(), a.out.resolve()))
