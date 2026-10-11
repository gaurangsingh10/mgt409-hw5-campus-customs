"""Campus Customs backend: FastAPI routes for the React dashboard.

Start (from backend/):   uvicorn main:app --reload --port 8000
   (or without activating the venv:  ../.venv/bin/uvicorn main:app --reload --port 8000)

Every read and write of shop data goes through the campus-customs MCP server,
the same one the agents use. The human-only tools (approve/reject, reset) are
only reachable from these routes, never from an agent.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
from models import TeamRunResult
from team import Team

team: Team | None = None
run_lock = asyncio.Lock()          # one team run at a time (token budget + DB writes)
running_ticket: int | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global team
    team = Team()
    async with team:               # one MCP server process for the app's lifetime
        yield
    team = None


app = FastAPI(title="Campus Customs Ops API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # The Vite dashboard (npm run dev) serves from http://localhost:5173. If that port is
    # busy Vite picks the next one, so any other local port is allowed too.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",  # local dashboards only
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


async def mcp(tool: str, args: dict | None = None) -> Any:
    """Call a campus-customs MCP tool directly (no LLM involved)."""
    if team is None:
        raise HTTPException(503, "Backend is still starting.")
    return await team.mcp.direct_call_tool(tool, args or {})


# ----------------------------------------------------------------- tickets


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": config.MODEL_NAME, "running_ticket": running_ticket}


@app.get("/api/tickets")
async def get_tickets() -> dict:
    """Every ticket with `state` open/resolved, its detailed status and pending approvals."""
    data = await mcp("list_tickets")
    return {"tickets": data["tickets"], "running_ticket": running_ticket}


@app.post("/api/tickets/{ticket_id}/run", response_model=TeamRunResult)
async def run_ticket(ticket_id: int) -> TeamRunResult:
    """Run the agent team (boss + delegates) on one ticket. Takes ~30-60 s; poll /api/events meanwhile.
    When the run finishes successfully the ticket is marked resolved."""
    global running_ticket
    ticket = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not ticket.get("found"):
        raise HTTPException(404, ticket.get("error", f"No ticket {ticket_id}."))
    if ticket["ticket"]["status"] == "resolved":
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved. Reset the database to run it again.")
    if run_lock.locked():
        raise HTTPException(409, f"The team is already working ticket {running_ticket}. Try again when it finishes.")
    async with run_lock:
        running_ticket = ticket_id
        try:
            result = await team.run_ticket(ticket_id)
        finally:
            running_ticket = None
    # The run a human started has finished: the board marks the ticket resolved.
    # (Done by the backend, not an agent. Pending approvals stay in the queue.)
    if result.ok:
        await mcp("human_resolve_ticket", {"ticket_id": ticket_id, "resolved_by": "desk",
                                           "note": f"team run {result.team_run_id} finished"})
    return result


# ------------------------------------------------------------------ events

_TICKET_IN_TASK = re.compile(r"ticket (\d+)", re.I)


def _ticket_of(entry: dict, team_tickets: dict[str, int]) -> int | None:
    # Entries written before Problem 7 have no ticket_id; recover it from the boss's task.
    return entry.get("ticket_id") or team_tickets.get(entry["team_run_id"])


def _simplify(e: dict, ticket_id: int | None) -> dict:
    """Turn a raw audit entry into what the board shows: who, what they said, which tools."""
    d = e.get("detail", {})
    out = {
        "ts": e["ts"], "ticket_id": ticket_id, "team_run_id": e["team_run_id"], "run_id": e["run_id"],
        "agent": e["agent"], "delegated_by": e.get("delegated_by"), "chain": e.get("chain", []),
        "step": e["step"], "event": e["event"], "said": None, "tools": [], "usage": e.get("usage", {}),
    }
    if e["event"] == "run_start":
        out["said"] = d.get("task")
    elif e["event"] == "model_response":
        calls = d.get("tool_calls", [])
        final = next((c for c in calls if c["tool"] == "final_result"), None)
        out["said"] = " ".join(d.get("text", [])) or (final["args"].get("summary") if final else None)
        out["tools"] = [{"tool": c["tool"], "args": c["args"]} for c in calls if c["tool"] != "final_result"]
    elif e["event"] == "tool_results":
        out["tools"] = [{"tool": r["tool"], "result": r["content"], "retry": r.get("retry", False)}
                        for r in d.get("results", [])]
    elif e["event"] == "delegation":
        out["said"] = d.get("task")
        out["delegation"] = {k: d.get(k) for k in ("from", "to", "refused", "reused_earlier_report")}
    elif e["event"] == "run_end":
        report = d.get("report", {})
        out["said"] = report.get("summary")
        out["report"] = report
    elif e["event"] == "error":
        out["said"] = f"{d.get('type')}: {d.get('message')}"
    elif e["event"] == "user_prompt":
        out["said"] = d.get("prompt")
    return out


@app.get("/api/events")
async def get_events(
    limit: int = Query(50, ge=1, le=500),
    since: str | None = Query(None, description="ISO ts; only events after it (for polling)"),
    ticket_id: int | None = None,
    team_run_id: str | None = None,
    agent: str | None = None,
) -> dict:
    """Recent agent events from output/audit_trail.json, newest last."""
    try:
        entries = json.loads(config.AUDIT_PATH.read_text()) if config.AUDIT_PATH.exists() else []
    except json.JSONDecodeError:
        entries = []   # file mid-rewrite is impossible (atomic replace), but never 500 the board
    team_tickets = {}
    for e in entries:
        if e["agent"] == "boss" and e["event"] == "run_start" and (m := _TICKET_IN_TASK.search(e["detail"].get("task", ""))):
            team_tickets.setdefault(e["team_run_id"], int(m.group(1)))

    picked = []
    for e in entries:
        tid = _ticket_of(e, team_tickets)
        if since and e["ts"] <= since:
            continue
        if ticket_id is not None and tid != ticket_id:
            continue
        if team_run_id and e["team_run_id"] != team_run_id:
            continue
        if agent and e["agent"] != agent:
            continue
        picked.append(_simplify(e, tid))
    picked = picked[-limit:]
    return {"count": len(picked), "latest_ts": picked[-1]["ts"] if picked else since,
            "running_ticket": running_ticket, "events": picked}


# --------------------------------------------------------------- approvals


class Decision(BaseModel):
    approver: str = Field(..., min_length=1, description="Name of the human clicking the button.")
    note: str = ""


@app.get("/api/approvals")
async def get_approvals(status: Literal["pending", "approved", "rejected", "all"] = "pending") -> dict:
    """Agent proposals waiting for (or decided by) a human."""
    return await mcp("list_approval_requests", {"status": status})


async def _decide(approval_id: int, decision: str, body: Decision) -> dict:
    result = await mcp("human_decide_approval", {"approval_id": approval_id, "decision": decision,
                                                 "approver": body.approver, "note": body.note})
    if not result.get("ok"):
        err = result.get("error", "")
        code = 404 if err.startswith("No approval request") else 409 if ("already" in err or "Not enough" in err) else 400
        raise HTTPException(code, err)
    return result


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: Decision) -> dict:
    """Human approves. For pay_invoice / pay_rent / restock_order this is the ONLY thing that
    writes a payment and lowers the checking balance."""
    return await _decide(approval_id, "approved", body)


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: Decision) -> dict:
    """Human rejects. No money moves."""
    return await _decide(approval_id, "rejected", body)


# -------------------------------------------------------------------- cash


@app.get("/api/cash")
async def get_cash() -> dict:
    """Current checking balance (cash_accounts) plus what's still owed."""
    pos = await mcp("get_cash_position")
    checking = next((a for a in pos["cash_accounts"] if a["name"] == "checking"), None)
    return {
        "account": "checking",
        "balance": checking["balance"] if checking else None,
        "as_of": checking["date"] if checking else None,
        "open_invoices_total": pos["open_invoices_total"],
        "rent_due_total": pos["rent_due_total"],
        "cash_after_all_obligations": pos["cash_after_all_obligations"],
        "cash_floor": 500.0,
    }


# ------------------------------------------------------------------- reset


@app.post("/api/reset")
async def reset() -> dict:
    """Restore data/campus_customs_new.db from the original. The audit trail is kept (append-only)."""
    if run_lock.locked():
        raise HTTPException(409, f"Can't reset while the team is working ticket {running_ticket}.")
    result = await mcp("human_reset_database")
    if not result.get("ok"):
        raise HTTPException(500, result.get("error"))
    return result
