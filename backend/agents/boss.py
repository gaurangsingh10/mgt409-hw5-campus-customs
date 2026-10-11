"""Boss agent: triages each ticket, delegates to specialists, reports to the human."""

from agents.spec import AgentSpec

SPEC = AgentSpec(
    name="boss",
    title="Boss",
    description="Triage and coordination: owns the ticket, routes work, consolidates the team's findings for the human.",
    mcp_tools=frozenset({
        "get_shop_date", "list_open_tickets", "get_ticket", "get_cash_position",
        "list_approval_requests", "update_ticket_status",
    }),
    approval_kinds=frozenset(),  # the boss delegates; specialists file the approvals
)
