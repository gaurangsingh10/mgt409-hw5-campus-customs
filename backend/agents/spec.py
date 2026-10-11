"""What every agent file declares: its role, its MCP tools and its approval rights."""

from dataclasses import dataclass, field

from models import AgentName, ApprovalKind


@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    title: str
    description: str                      # shown to other agents in the delegate tool
    mcp_tools: frozenset[str]             # least privilege: only these MCP tools are visible
    approval_kinds: frozenset[ApprovalKind] = field(default_factory=frozenset)
