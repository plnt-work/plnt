from plnt import ToolContext, tool


@tool
def lookup_order(order_id: str, ctx: ToolContext, include_items: bool = False) -> dict:
    """Look up an order's status by id.

    Second paragraph is not part of the description.
    """
    return {
        "order_id": order_id,
        "status": "shipped",
        "shop": ctx.config["shop_name"],
        "key_tail": ctx.secret("SHOP_API_KEY")[-4:],
        "tenant": ctx.tenant_id,
        "items": ["mug"] if include_items else None,
    }
