"""Accounting agent: cash, vendor invoices, discount math, invoice payments."""

from agents.spec import AgentSpec

SPEC = AgentSpec(
    name="accounting",
    title="Accounting",
    description="Cash on hand, vendor invoices and overdue bills, discount/margin math, invoice payment and price-override proposals.",
    mcp_tools=frozenset({
        "get_shop_date", "get_ticket", "get_cash_position", "get_invoice", "quote_bulk_order",
        "list_vendors", "list_approval_requests", "submit_approval_request",
    }),
    approval_kinds=frozenset({"pay_invoice", "price_override"}),
)
