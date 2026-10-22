"""The Gemini-powered food ordering agent.

Each customer gets a Gemini chat session with tools (search the menu, add to cart,
place an order...). The google-genai SDK calls our Python tool functions
automatically and feeds the results back until Gemini writes its reply.

The previous Claude version is kept in agent_claude.py.
"""

from google import genai
from google.genai import errors, types

import store

# Tried in order. If a model is overloaded (503), times out (504) or hits a rate
# limit (429), the next one takes over with the same conversation.
MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]
BUSY_CODES = {429, 503, 504}

_client = None


def get_client() -> genai.Client:
    """Create the client on first use so the site still loads without a key."""
    global _client
    if _client is None:
        _client = genai.Client(  # reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment
            http_options=types.HttpOptions(
                timeout=60_000,  # ms; give up on a stuck request after 60s
                # One retry at most. The SDK's default retries can wait many minutes
                # when a model is busy; switching models is faster.
                retry_options=types.HttpRetryOptions(attempts=2, max_delay=5),
            ),
        )
    return _client


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
- If a tool returns an "error", explain the problem to the customer in plain words.
- Keep replies short and warm, like a chat message. Use simple lists for menus. No markdown headings or bold text.
- Politely decline topics unrelated to food or this restaurant."""


def _safe(fn):
    """Return errors to Gemini as data. A raised exception would abort the whole reply."""
    try:
        return fn()
    except (ValueError, TypeError) as err:
        return {"error": str(err)}


def make_tools(session: store.Session) -> list:
    """Build tool functions bound to one customer's cart.

    Gemini reads each function's name, type hints and docstring to decide when
    and how to call it, so keep those accurate.
    """

    def search_menu(query: str = "", category: str = "", veg_only: bool = False,
                    max_price: int = 0, max_spice: int = 3) -> dict:
        """Search the restaurant menu. Call with no arguments to get the full menu.

        Args:
            query: Keywords, e.g. 'paneer', 'biryani', 'cold drink'. Empty for everything.
            category: One of Starters, Mains, Breads, Desserts, Drinks. Empty for all.
            veg_only: True to show only vegetarian dishes.
            max_price: Maximum price in rupees. 0 means no limit.
            max_spice: Maximum spice level from 0 (mild) to 3 (very spicy).

        Returns:
            Matching items with id, name, price, veg flag and spice level.
        """
        items = store.search_menu(query, category, veg_only, max_price or None, max_spice)
        return {"count": len(items), "items": items}

    def add_to_cart(item_id: str, quantity: int = 1, notes: str = "") -> dict:
        """Add a menu item to the customer's cart.

        Args:
            item_id: Menu item id from search_menu, e.g. 'M1'.
            quantity: How many to add.
            notes: Special instructions, e.g. 'less spicy'.

        Returns:
            The updated cart with totals.
        """
        return _safe(lambda: store.add_to_cart(session, item_id, quantity, notes))

    def update_cart_item(item_id: str, quantity: int) -> dict:
        """Change the quantity of an item already in the cart. Quantity 0 removes it.

        Args:
            item_id: Menu item id, e.g. 'M1'.
            quantity: New quantity. 0 removes the item.

        Returns:
            The updated cart with totals.
        """
        return _safe(lambda: store.update_cart_item(session, item_id, quantity))

    def view_cart() -> dict:
        """Show the current cart with subtotal, tax, delivery fee and total."""
        return store.cart_summary(session)

    def place_order(customer_name: str, phone: str, address: str, payment_method: str) -> dict:
        """Place the order for everything in the cart. Only call after the customer
        has confirmed the cart and given their details.

        Args:
            customer_name: Customer's name.
            phone: 10-digit phone number.
            address: Full delivery address.
            payment_method: One of cash, upi, card.

        Returns:
            The order id, total and estimated delivery time in minutes.
        """
        return _safe(lambda: store.place_order(session, customer_name, phone, address,
                                               payment_method.lower().strip()))

    def track_order(order_id: str) -> dict:
        """Get the delivery status of an order.

        Args:
            order_id: The order id, which looks like SG123456.

        Returns:
            The order status and items.
        """
        return _safe(lambda: store.track_order(order_id))

    return [search_menu, add_to_cart, update_cart_item, view_cart, place_order, track_order]


def chat(session: store.Session, user_text: str) -> str:
    """Send one customer message through the agent and return its reply."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=make_tools(session),
        # The SDK runs our functions for us; cap the rounds per message.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=10),
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),  # chat: favour speed
    )
    last_error = None
    for model in MODELS:
        if session.gemini_chat is None or session.gemini_model != model:
            # Start (or move) the chat on this model, keeping earlier messages.
            history = session.gemini_chat.get_history() if session.gemini_chat else None
            session.gemini_chat = get_client().chats.create(model=model, config=config, history=history)
            session.gemini_model = model
        try:
            response = session.gemini_chat.send_message(user_text)
        except errors.APIError as err:
            if err.code not in BUSY_CODES:
                raise
            last_error = err  # this model is busy; try the next one
            continue
        text = (response.text or "").strip()
        return text or "Sorry, I didn't catch that. Could you say it again?"
    raise last_error
