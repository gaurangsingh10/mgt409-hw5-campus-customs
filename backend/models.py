"""Data types shared by the Campus Customs agent team."""

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

ApprovalKind = Literal["pay_invoice", "pay_rent", "price_override", "restock_order", "customer_reply"]


class ApprovalRef(BaseModel):
    """An approval request an agent filed through the MCP server."""

    approval_id: int
    kind: ApprovalKind
    amount: float | None = None
    summary: str


class AgentReport(BaseModel):
    """What every agent returns at the end of its loop (its structured output)."""

    agent: AgentName
    ticket_ids: list[int] = Field(default_factory=list)
    summary: str = Field(description="2-4 plain sentences: what's going on and what the human must decide.")
    facts: list[str] = Field(default_factory=list, description="Key facts, each tagged with the tool it came from.")
    actions_taken: list[str] = Field(default_factory=list)
    approvals_requested: list[ApprovalRef] = Field(default_factory=list)
    needs_human: bool = False
    open_questions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


AuditEvent = Literal[
    "run_start",       # an agent loop begins (task text, who delegated it)
    "user_prompt",     # the task handed to the model
    "model_response",  # what the model decided this step: text and/or tool calls
    "tool_results",    # tool outputs sent back to the model for the next step
    "delegation",      # one agent handing work to another (or a refused hand-off)
    "run_end",         # final AgentReport + usage
    "error",           # anything that stopped a loop (budget hit, API error...)
]


class AuditEntry(BaseModel):
    """One line in output/audit_trail.json. One per agent-loop step."""

    ts: str
    team_run_id: str = Field(description="One id per top-level ticket run; shared by every agent in it.")
    run_id: str = Field(description="One id per agent loop.")
    ticket_id: int | None = Field(default=None, description="The ticket this team run is working.")
    agent: AgentName
    delegated_by: AgentName | None = None
    chain: list[AgentName] = Field(description="Delegation path from the boss to this agent.")
    step: int
    event: AuditEvent
    model: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict, description="Token usage for this step / run.")


class TeamRunResult(BaseModel):
    team_run_id: str
    ticket_id: int | None
    ok: bool
    report: AgentReport | None = None
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
