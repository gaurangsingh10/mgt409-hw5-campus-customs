"""Facilities agent: the Chapel Street lease, rent, landlord notices."""

from agents.spec import AgentSpec

SPEC = AgentSpec(
    name="facilities",
    title="Facilities",
    description="The shop lease, rent amounts and due dates, verifying landlord notices, rent payment proposals.",
    mcp_tools=frozenset({
        "get_shop_date", "get_ticket", "get_lease_rent_status", "get_cash_position",
        "list_approval_requests", "submit_approval_request",
    }),
    approval_kinds=frozenset({"pay_rent"}),
)
