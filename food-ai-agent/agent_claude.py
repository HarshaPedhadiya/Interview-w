"""The Claude-powered food ordering agent.

It runs a tool-use loop: Claude decides which tool to call (search the menu,
add to cart, place an order...), we run it against store.py, send the result
back, and repeat until Claude writes its final reply to the customer.
"""

import json

import anthropic

import store

MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 10

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

R = store.RESTAURANT
SYSTEM_PROMPT = f"""You are the friendly ordering assistant for {R['name']}, an Indian restaurant that delivers food.
Opening hours: {R['hours']}. Prices are in Indian rupees ({R['currency']}).
Delivery costs {R['currency']}{R['delivery_fee']}, free on orders of {R['currency']}{R['free_delivery_above']} or more. 5% GST is added.

What you do:
- Help customers discover dishes, answer questions about ingredients, spice level and veg/non-veg, and recommend combos.
- Manage their cart and place orders using your tools. Always look items up with search_menu rather than guessing ids or prices.
- Track existing orders by order id.

Rules:
- Only offer dishes that exist on the menu. If something is not available, say so and suggest the closest match.
- Before calling place_order, show the cart total and collect name, 10-digit phone, delivery address and payment method (cash, upi or card). Get a clear "yes" from the customer first.
- If a customer mentions an allergy, point out which dishes might contain it and suggest they confirm with the restaurant; do not promise a dish is allergen-free.
- Keep replies short and warm, like a chat message. Use simple lists for menus. No markdown headings.
- Politely decline topics unrelated to food or this restaurant."""

TOOLS = [
    {
        "name": "search_menu",
        "description": "Search the restaurant menu. All filters are optional; call with no arguments to get the full menu. Returns item ids, prices, veg flag and spice level (0 = mild, 3 = very spicy).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords, e.g. 'paneer', 'biryani', 'cold drink'."},
                "category": {"type": "string", "enum": ["Starters", "Mains", "Breads", "Desserts", "Drinks"]},
                "veg_only": {"type": "boolean"},
                "max_price": {"type": "number", "description": "Maximum price in rupees."},
                "max_spice": {"type": "integer", "description": "Maximum spice level, 0-3."},
            },
        },
    },
    {
        "name": "add_to_cart",
        "description": "Add a menu item to the customer's cart. Returns the updated cart with totals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Menu item id from search_menu, e.g. 'M1'."},
                "quantity": {"type": "integer", "description": "How many to add (default 1)."},
                "notes": {"type": "string", "description": "Special instructions, e.g. 'less spicy'."},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "update_cart_item",
        "description": "Change the quantity of an item already in the cart. Quantity 0 removes it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "quantity": {"type": "integer"},
            },
            "required": ["item_id", "quantity"],
        },
    },
    {
        "name": "view_cart",
        "description": "Show the current cart with subtotal, tax, delivery fee and total.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "place_order",
        "description": "Place the order for everything in the cart. Only call after the customer has confirmed the cart and given their details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "phone": {"type": "string"},
                "address": {"type": "string"},
                "payment_method": {"type": "string", "enum": ["cash", "upi", "card"]},
            },
            "required": ["customer_name", "phone", "address", "payment_method"],
        },
    },
    {
        "name": "track_order",
        "description": "Get the delivery status of an order by its id (looks like SG123456).",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
]


def run_tool(session: store.Session, name: str, args: dict):
    """Execute one tool call against the store. Raises ValueError on bad input."""
    if name == "search_menu":
        items = store.search_menu(**args)
        return {"count": len(items), "items": items}
    if name == "add_to_cart":
        return store.add_to_cart(session, **args)
    if name == "update_cart_item":
        return store.update_cart_item(session, **args)
    if name == "view_cart":
        return store.cart_summary(session)
    if name == "place_order":
        return store.place_order(session, **args)
    if name == "track_order":
        return store.track_order(**args)
    raise ValueError(f"Unknown tool: {name}")


def chat(session: store.Session, user_text: str) -> str:
    """Send one customer message through the agent and return its reply."""
    messages = session.messages
    start = len(messages)
    messages.append({"role": "user", "content": user_text})
    try:
        return _run_loop(session, messages)
    except Exception:
        del messages[start:]  # drop the failed turn so the next message starts clean
        raise


def _run_loop(session: store.Session, messages: list) -> str:
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},  # chat: fast replies are worth more than deep thinking
            cache_control={"type": "ephemeral"},  # cache the growing conversation between turns
            # If a safety classifier declines, the API retries on a suitable model automatically.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        # Keep the full content (thinking, tool calls, fallback blocks) in history.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            return "Sorry, I can't help with that. I'm happy to help with our menu or your order!"

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_calls:
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            return text or "Sorry, I didn't catch that. Could you say it again?"

        # Run every tool call, then send all results back in one message.
        results = []
        for call in tool_calls:
            try:
                output = run_tool(session, call.name, dict(call.input or {}))
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": json.dumps(output, ensure_ascii=False)})
            except (ValueError, TypeError) as err:
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": f"Error: {err}", "is_error": True})
        messages.append({"role": "user", "content": results})

    return "Sorry, that took too many steps. Could you rephrase your request?"
