"""The Gemini-powered travel planning agent.

Each visitor gets a Gemini chat session with tools (search destinations, check
weather, estimate a budget, save a trip...). The google-genai SDK calls our
Python tool functions automatically and feeds the results back until Gemini
writes its reply.
"""

from datetime import date

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
                timeout=60_000,  # ms
                retry_options=types.HttpRetryOptions(attempts=2, max_delay=5),
            ),
        )
    return _client


def system_prompt() -> str:
    today = date.today().strftime("%A, %d %B %Y")
    return f"""You are Wanderly, a friendly travel planning assistant for trips within India.
Today is {today}. Prices are in Indian rupees ({store.CURRENCY}).

What you do:
- Suggest destinations that fit the traveller's month, interests and budget.
- Check the weather for their travel month and warn about monsoon, extreme heat or closed roads.
- Build realistic day-by-day itineraries from the destination's attractions.
- Estimate the trip budget and save finished plans so the traveller can see them under "My trips".

How to work:
- Always use your tools for destination facts, attractions, weather and costs. Never invent prices or attractions.
- If key details are missing (where or what kind of trip, when, how many days, how many people, budget level), ask for them briefly. Ask at most 2 questions at a time.
- Plan realistic days: about 6-8 hours of activities, group nearby places, and use each attraction's "hours" to size the day. Day 1 includes arrival; the last day includes departure.
- Show the plan as "Day 1: ...", "Day 2: ..." with the budget estimate, then ask if they want to save it or change anything.
- Only call save_trip after the traveller agrees. Pass one short paragraph per day in day_plans.
- If the traveller asks about a place you have no data for, say so and suggest the closest destination you do cover.
- If a tool returns an "error", explain the problem in plain words.
- Keep replies short and friendly, like a chat message. Use simple lists. No markdown headings, bold text or tables.
- Politely decline topics unrelated to travel."""


def _safe(fn):
    """Return errors to Gemini as data. A raised exception would abort the whole reply."""
    try:
        return fn()
    except (ValueError, TypeError) as err:
        return {"error": str(err)}


def make_tools(session: store.Session) -> list:
    """Build tool functions bound to one visitor's saved trips.

    Gemini reads each function's name, type hints and docstring to decide when
    and how to call it, so keep those accurate.
    """

    def search_destinations(query: str = "", trip_type: str = "", month: str = "",
                            max_daily_budget: int = 0) -> dict:
        """Find destinations. Call with no arguments to list every destination.

        Args:
            query: Keywords, e.g. 'lake', 'Rajasthan', 'yoga'. Empty for all.
            trip_type: One of beach, mountains, heritage, culture, spiritual, adventure,
                nature, relaxation, romantic, snow, shopping, nightlife, road trip. Empty for all.
            month: Travel month, e.g. 'December'. Only returns places that are good that month. Empty for any.
            max_daily_budget: Max cost per person per day in rupees at budget level. 0 means no limit.

        Returns:
            Matching destinations with id, best months and starting cost per day.
        """
        return _safe(lambda: {"results": store.search_destinations(query, trip_type, month, max_daily_budget)})

    def get_destination_details(destination_id: str) -> dict:
        """Get full details for one destination: attractions (with entry fee and hours
        needed), best months, how to get there and tips.

        Args:
            destination_id: Id from search_destinations, e.g. 'jaipur'.
        """
        def run():
            d = store.get_destination(destination_id)
            return {**store.card(d), "getting_there": d["getting_there"],
                    "tips": d.get("tips", ""), "attractions": d["attractions"]}
        return _safe(run)

    def get_weather(destination_id: str, month: str) -> dict:
        """Get typical weather for a destination in a given month and whether it's a good time to go.

        Args:
            destination_id: Destination id, e.g. 'manali'.
            month: Month name, e.g. 'July'.
        """
        return _safe(lambda: store.weather(destination_id, month))

    def estimate_budget(destination_id: str, days: int, travellers: int, budget_level: str = "mid") -> dict:
        """Estimate the cost of stay, food and local transport for a trip.

        Args:
            destination_id: Destination id, e.g. 'goa'.
            days: Number of days.
            travellers: Number of people.
            budget_level: One of budget, mid, luxury.

        Returns:
            Cost breakdown, total and per-person cost in rupees.
        """
        return _safe(lambda: store.estimate_budget(destination_id, days, travellers, budget_level))

    def save_trip(destination_id: str, days: int, travellers: int, budget_level: str,
                  start_date: str, day_plans: list[str], title: str = "") -> dict:
        """Save a finished itinerary to the traveller's "My trips" list.
        Only call after the traveller has agreed to the plan.

        Args:
            destination_id: Destination id, e.g. 'udaipur'.
            days: Number of days. Must equal the number of day_plans.
            travellers: Number of people.
            budget_level: One of budget, mid, luxury.
            start_date: Start date as the traveller gave it, e.g. '12 Dec 2026' or 'mid December'.
            day_plans: One short paragraph per day, in order.
            title: Short trip name, e.g. 'Udaipur anniversary getaway'.

        Returns:
            The saved trip with its id and estimated total.
        """
        return _safe(lambda: store.save_trip(session, destination_id, days, travellers,
                                             budget_level, start_date, day_plans, title))

    def list_saved_trips() -> dict:
        """List the traveller's saved trips with their day-by-day plans."""
        return {"trips": list(session.trips.values())}

    def delete_saved_trip(trip_id: str) -> dict:
        """Delete a saved trip. Confirm with the traveller first.

        Args:
            trip_id: Trip id, which looks like TR12345.
        """
        return _safe(lambda: store.delete_trip(session, trip_id))

    return [search_destinations, get_destination_details, get_weather, estimate_budget,
            save_trip, list_saved_trips, delete_saved_trip]


def chat(session: store.Session, user_text: str) -> str:
    """Send one visitor message through the agent and return its reply."""
    config = types.GenerateContentConfig(
        system_instruction=system_prompt(),
        tools=make_tools(session),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=12),
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
    )
    last_error = None
    for model in MODELS:
        if session.gemini_chat is None or session.gemini_model != model:
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
