"""Customer Service agent: drafts honest replies to customers for approval."""

from agents.spec import AgentSpec

SPEC = AgentSpec(
    name="customer_service",
    title="Customer Service",
    description="Talks to customers and student orgs: explains options honestly and drafts replies for human approval.",
    mcp_tools=frozenset({
        "get_shop_date", "get_ticket", "check_stock", "quote_bulk_order",
        "list_approval_requests", "submit_approval_request",
    }),
    approval_kinds=frozenset({"customer_reply"}),
)
