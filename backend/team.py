"""The Campus Customs agent team: five pydantic-ai agents, one MCP connection.

- Every shop fact comes from the campus-customs MCP server (HW5/.mcp.json),
  which is the only layer that touches data/campus_customs_new.db.
- Every agent can delegate to every other agent (full connectivity) through the
  `delegate` tool, with loop/depth/budget guards.
- Every agent-loop step is appended to output/audit_trail.json.

Usage:
    async with Team() as team:
        result = await team.run_ticket(101)
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import config
from agents import SPECS
from audit import AuditTrail, now_iso
from models import AGENT_NAMES, AgentName, AgentReport, AuditEntry, TeamRunResult

from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, RunContext, Tool, UsageLimits
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage


@dataclass
class TeamDeps:
    """Per-agent-run context, visible to tools via RunContext.deps."""

    team_run_id: str
    run_id: str
    agent: AgentName
    chain: tuple[AgentName, ...]   # delegation path, boss first
    ticket_id: int | None = None
    delegations: int = 0

    @property
    def max_delegations(self) -> int:
        return config.MAX_DELEGATIONS_BOSS if self.agent == "boss" else config.MAX_DELEGATIONS_SPECIALIST


def _clip(value: Any, limit: int = config.AUDIT_TEXT_LIMIT) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= limit:
        return value
    return text[:limit] + f"... [truncated {len(text) - limit} chars]"


def _usage_dict(u: Any) -> dict:
    return {k: getattr(u, k, None) for k in ("requests", "tool_calls", "input_tokens", "output_tokens")
            if getattr(u, k, None) is not None}


class Team:
    def __init__(self, audit_path=config.AUDIT_PATH):
        api_key = os.getenv("PORTKEY_API_KEY")
        if not api_key:
            raise RuntimeError("PORTKEY_API_KEY is not set. Put it in HW5/.env (see .env.example).")
        provider = OpenAIProvider(base_url=config.PORTKEY_BASE_URL, api_key=api_key)
        # Responses API: Azure (behind Portkey) rejects function tools + reasoning on
        # /v1/chat/completions for gpt-6-luna, but allows them on /v1/responses.
        self.model = OpenAIResponsesModel(config.MODEL_NAME, provider=provider)
        self.audit = AuditTrail(audit_path)
        self.limits = UsageLimits(
            request_limit=config.TEAM_REQUEST_LIMIT,
            tool_calls_limit=config.TEAM_TOOL_CALLS_LIMIT,
            total_tokens_limit=config.TEAM_TOTAL_TOKENS_LIMIT,
        )

        # One MCP server process for the whole team, launched exactly as .mcp.json says.
        server = config.mcp_server_config()
        self.mcp = MCPToolset(
            StdioTransport(command=server["command"], args=server.get("args", []),
                           env=server.get("env"), cwd=server.get("cwd")),
            id=config.MCP_SERVER_NAME,
            process_tool_call=self._guard_mcp_call,
        )
        # Reports already produced in a team run: re-asking an agent returns its report
        # instead of paying for the same work twice.
        self._reports: dict[str, dict[AgentName, AgentReport]] = {}
        self.agents: dict[AgentName, Agent[TeamDeps, AgentReport]] = {
            name: self._build_agent(name) for name in AGENT_NAMES
        }

    async def __aenter__(self) -> "Team":
        await self.mcp.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.mcp.__aexit__(*exc)

    # ------------------------------------------------------------------ build

    def _build_agent(self, name: AgentName) -> Agent[TeamDeps, AgentReport]:
        spec = SPECS[name]
        allowed = spec.mcp_tools
        others = "\n".join(f"- {s.name}: {s.description}" for s in SPECS.values() if s.name != name)
        delegate_tool = Tool(
            self._delegate,
            name="delegate",
            description=(
                "Hand a specific sub-task to another Campus Customs agent and get its report back.\n"
                f"Agents you can reach:\n{others}\n"
                "Give the ticket id and the exact ids/SKUs/sizes they need. "
                f"Limits: {config.MAX_DELEGATIONS_BOSS if name == 'boss' else config.MAX_DELEGATIONS_SPECIALIST} "
                f"delegation(s) per run, depth {config.MAX_DELEGATION_DEPTH}, you can't hand work back to an agent "
                "that's already above you in the chain, and an agent that already reported on this ticket "
                "returns its earlier report instead of redoing the work."
            ),
        )
        return Agent(
            self.model,
            name=name,
            instructions=(config.PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"),
            deps_type=TeamDeps,
            output_type=AgentReport,
            toolsets=[self.mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)],
            tools=[delegate_tool],
            model_settings=ModelSettings(max_tokens=config.MAX_OUTPUT_TOKENS),
            retries=2,
        )

    # ------------------------------------------------------------- guardrails

    async def _guard_mcp_call(self, ctx: RunContext[TeamDeps], call_tool, name: str, args: dict) -> Any:
        """Runs before every MCP call: enforce tool access and approval rights, stamp identity.

        Human-only tools (human_decide_approval, human_reset_database, list_tickets) are in
        no agent's allowlist, so an agent can never reach them even by guessing the name.
        """
        agent = ctx.deps.agent
        spec = SPECS[agent]
        if name not in spec.mcp_tools:
            return {"ok": False, "error": f"{agent} is not allowed to use {name}."}
        if name == "submit_approval_request":
            if args.get("kind") not in spec.approval_kinds:
                return {"ok": False, "error": f"{agent} may only file approval kinds {sorted(spec.approval_kinds)}. "
                                              "Delegate to the agent who owns that kind."}
            args = {**args, "requested_by": agent}   # agents can't sign as someone else
        if name == "update_ticket_status":
            args = {**args, "agent": agent}
        return await call_tool(name, args)

    # ------------------------------------------------------------- delegation

    async def _delegate(self, ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict:
        d = ctx.deps
        refusal = None
        if to_agent == d.agent:
            refusal = "You can't delegate to yourself."
        elif to_agent in d.chain:
            refusal = (f"{to_agent} is already above you in this chain ({' -> '.join(d.chain)}). "
                       "Finish with what you have and let your report go back up.")
        elif len(d.chain) > config.MAX_DELEGATION_DEPTH:
            refusal = f"Max delegation depth ({config.MAX_DELEGATION_DEPTH}) reached. Finish with what you have."
        elif d.delegations >= d.max_delegations:
            refusal = f"You've used all {d.max_delegations} delegation(s) for this run. Finish with what you have."

        cached = self._reports.get(d.team_run_id, {}).get(to_agent)
        self._log(d, step=-1, event="delegation",
                  detail={"from": d.agent, "to": to_agent, "task": task, "refused": refusal,
                          "reused_earlier_report": bool(cached and not refusal)})
        if refusal:
            return {"ok": False, "refused": refusal}
        if cached:
            return {"ok": True, "reused": True,
                    "note": f"{to_agent} already reported on this ticket in this run; here is that report.",
                    "report": cached.model_dump()}

        d.delegations += 1
        try:
            report = await self.run_agent(to_agent, task, team_run_id=d.team_run_id,
                                          chain=(*d.chain, to_agent), usage=ctx.usage, ticket_id=d.ticket_id)
        except Exception as e:  # child failed (budget, API...) - tell the caller, don't crash it
            return {"ok": False, "error": f"{to_agent} failed: {type(e).__name__}: {e}"}
        return {"ok": True, "report": report.model_dump()}

    # -------------------------------------------------------------- the loop

    def _log(self, deps: TeamDeps, step: int, event: str, detail: dict | None = None,
             usage: dict | None = None, model: str | None = None) -> None:
        self.audit.append(AuditEntry(
            ts=now_iso(), team_run_id=deps.team_run_id, run_id=deps.run_id, ticket_id=deps.ticket_id, agent=deps.agent,
            delegated_by=deps.chain[-2] if len(deps.chain) > 1 else None, chain=list(deps.chain),
            step=step, event=event, model=model, detail=detail or {}, usage=usage or {},
        ))

    async def run_agent(self, name: AgentName, task: str, *, team_run_id: str,
                        chain: tuple[AgentName, ...], usage: RunUsage, ticket_id: int | None = None) -> AgentReport:
        """One agent loop (model -> tools -> model ... -> AgentReport), audited step by step."""
        deps = TeamDeps(team_run_id=team_run_id, run_id=f"{name}-{uuid.uuid4().hex[:8]}", agent=name,
                        chain=chain, ticket_id=ticket_id)
        # This run's own usage, summed from its model responses (the shared `usage`
        # counter also includes sibling agents running in parallel).
        mine = {"requests": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0}
        prompt = task if len(chain) == 1 else f"[Delegated to you by {chain[-2]}]\n{task}"
        self._log(deps, 0, "run_start", {"task": task, "depth": len(chain) - 1, "model": config.MODEL_NAME})

        step = 0
        try:
            async with self.agents[name].iter(prompt, deps=deps, usage=usage, usage_limits=self.limits) as run:
                async for node in run:
                    if Agent.is_user_prompt_node(node):
                        step += 1
                        self._log(deps, step, "user_prompt", {"prompt": _clip(node.user_prompt)})
                    elif Agent.is_model_request_node(node):
                        results = [
                            {"tool": p.tool_name, "tool_call_id": p.tool_call_id,
                             "retry": isinstance(p, RetryPromptPart), "content": _clip(p.content)}
                            for p in node.request.parts if isinstance(p, (ToolReturnPart, RetryPromptPart))
                        ]
                        if results:
                            step += 1
                            self._log(deps, step, "tool_results", {"results": results})
                    elif Agent.is_call_tools_node(node):
                        step += 1
                        resp = node.model_response
                        calls = [p for p in resp.parts if isinstance(p, ToolCallPart)]
                        mine["requests"] += 1
                        mine["tool_calls"] += len(calls)
                        mine["input_tokens"] += resp.usage.input_tokens or 0
                        mine["output_tokens"] += resp.usage.output_tokens or 0
                        self._log(
                            deps, step, "model_response",
                            detail={
                                "text": [_clip(p.content) for p in resp.parts if isinstance(p, TextPart)],
                                "tool_calls": [{"tool": p.tool_name, "tool_call_id": p.tool_call_id,
                                                "args": p.args_as_dict()}
                                               for p in calls],
                                "finish_reason": getattr(resp, "finish_reason", None),
                            },
                            usage=_usage_dict(resp.usage),
                            model=resp.model_name,
                        )
                report = run.result.output.model_copy(update={"agent": name})
        except Exception as e:
            self._log(deps, step + 1, "error", {"type": type(e).__name__, "message": _clip(str(e))})
            raise

        self._reports.setdefault(team_run_id, {})[name] = report
        self._log(deps, step + 1, "run_end", {"report": report.model_dump()},
                  usage={"this_run": mine, "team_total_so_far": _usage_dict(usage)})
        return report

    async def run_ticket(self, ticket_id: int) -> TeamRunResult:
        """Top-level entry: the boss works one ticket with the whole team."""
        team_run_id = f"team-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
        usage = RunUsage()
        task = (f"Work ticket {ticket_id}. Follow your process: check the shop date and the ticket, "
                "delegate to the right specialists, make sure every money or customer action is filed "
                "as an approval request, update the ticket status, and report back to me.")
        try:
            report = await self.run_agent("boss", task, team_run_id=team_run_id, chain=("boss",), usage=usage,
                                          ticket_id=ticket_id)
            return TeamRunResult(team_run_id=team_run_id, ticket_id=ticket_id, ok=True,
                                 report=report, usage=_usage_dict(usage))
        except Exception as e:
            return TeamRunResult(team_run_id=team_run_id, ticket_id=ticket_id, ok=False,
                                 error=f"{type(e).__name__}: {e}", usage=_usage_dict(usage))
        finally:
            self._reports.pop(team_run_id, None)
