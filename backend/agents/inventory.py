"""Inventory agent: stock by SKU/size, vendors, lead times, restock proposals."""

from agents.spec import AgentSpec

SPEC = AgentSpec(
    name="inventory",
    title="Inventory",
    description="Stock on hand by SKU and size, aisle locations, vendors and lead times, restock proposals.",
    mcp_tools=frozenset({
        "get_shop_date", "get_ticket", "check_stock", "list_vendors", "get_invoice",
        "list_approval_requests", "submit_approval_request",
    }),
    approval_kinds=frozenset({"restock_order"}),
)
