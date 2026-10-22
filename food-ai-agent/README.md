# Spice Garden AI Food Agent

A food-ordering website with a Google Gemini-powered chat assistant. Customers can ask for
recommendations ("veg dishes under ₹250", "something mild for kids"), build a cart,
place an order, and track it, all by chatting.

## Run it

1. Install the packages: `pip install -r requirements.txt`
2. Copy `.env.example` to a new file named `.env` and paste your Gemini key after `GEMINI_API_KEY=`
   (free key at https://aistudio.google.com/apikey). `.env` is in `.gitignore`, so your key is never uploaded.
3. Start the server: `python -m uvicorn app:app --reload`

Open http://127.0.0.1:8000 and click **Chat to order**.

## Files

| File | What it does |
|---|---|
| `agent.py` | The agent: system prompt, tool functions, and the Gemini chat (`gemini-3.6-flash`, with `gemini-3.5-flash-lite` as backup) |
| `agent_claude.py` | The earlier Claude version, kept as a backup (not used by the server) |
| `store.py` | Menu, carts, orders (in memory). Replace with your database for a real site |
| `app.py` | FastAPI server: `/api/chat`, `/api/menu`, `/api/cart/{id}` |
| `static/index.html` | The website: menu grid, live cart, chat widget |

## Agent tools

`search_menu`, `add_to_cart`, `update_cart_item`, `view_cart`, `place_order`, `track_order`.
They are plain Python functions in `make_tools()`. Gemini reads their names, type hints and
docstrings to decide when to call them, and the SDK runs them automatically.

## Customising

- **Your own menu:** edit `MENU` and `RESTAURANT` in `store.py`.
- **Assistant personality/rules:** edit `SYSTEM_PROMPT` in `agent.py`.
- **Different model:** edit `MODELS` in `agent.py`. The first is used normally; the next ones take over automatically when a model is busy.
- **New abilities** (table booking, coupons...): add a function inside `make_tools()` and include it in the returned list.
- **Production:** carts and orders reset when the server restarts. Move them to a database, and add real payment handling before taking money.
