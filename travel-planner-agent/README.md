# Wanderly AI Travel Planner Agent

A trip-planning website with a Google Gemini-powered chat assistant. Travellers can ask
"where should I go in December?", check the weather for their month, get a day-by-day
itinerary with a budget estimate, and save the plan to **My trips**, all by chatting.

## Run it

1. Open a terminal **in this folder** (`travel-planner-agent`).
2. Install the packages: `pip install -r requirements.txt`
3. Copy `.env.example` to a new file named `.env` and paste your Gemini key after `GEMINI_API_KEY=`
   (free key at https://aistudio.google.com/apikey). `.env` is in `.gitignore`, so your key is never uploaded.
4. Start the server: `python -m uvicorn app:app --reload`

Open http://127.0.0.1:8000 and click **Plan a trip with AI**.

## Files

| File | What it does |
|---|---|
| `agent.py` | The agent: system prompt, tool functions, and the Gemini chat (with a backup model if the first is busy) |
| `store.py` | Destinations, attractions, monthly weather, cost tables, budget maths and saved trips (in memory) |
| `app.py` | FastAPI server: `/api/chat`, `/api/destinations`, `/api/trips/{id}` |
| `static/index.html` | The website: destination cards, My trips panel, chat widget |

## Agent tools

| Tool | What it does |
|---|---|
| `search_destinations` | Filter by keyword, trip type, travel month and daily budget |
| `get_destination_details` | Attractions (entry fee, hours needed), how to get there, tips |
| `get_weather` | Typical temperature and conditions for a month, and whether it's a good time |
| `estimate_budget` | Stay, food and local transport cost for days × people × budget level |
| `save_trip` | Saves an agreed itinerary to My trips |
| `list_saved_trips` / `delete_saved_trip` | View or remove saved trips |

They are plain Python functions in `make_tools()`. Gemini reads their names, type hints and
docstrings to decide when to call them, and the SDK runs them automatically.

## How a conversation flows

1. The user says "4 days in Rajasthan in January, 2 people, mid budget".
2. Gemini calls `search_destinations(query="Rajasthan", month="January")` and gets Jaipur and Udaipur.
3. It calls `get_weather` and `get_destination_details` for the chosen city, then `estimate_budget`.
4. It replies with Day 1 to Day 4 and the total cost. When the user says "save it", it calls `save_trip`.
5. The page refreshes the My trips panel from the `trips` field in the chat response.

## Customising

- **More destinations:** add entries to `DESTINATIONS` in `store.py`.
- **Prices:** edit `COSTS` in `store.py`.
- **Assistant personality/rules:** edit `system_prompt()` in `agent.py`.
- **Real data:** replace `store.weather` with a weather API and `COSTS` with a hotel or flight API.
- **Production:** saved trips reset when the server restarts. Move them to a database.
