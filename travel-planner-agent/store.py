"""Destination data, budget maths, and saved trips for the travel planner.

Everything lives in memory so the project runs with no database.
Swap these functions for real DB or API calls (weather, hotels) when you build it out.
"""

import math
import random
import string
from dataclasses import dataclass, field

CURRENCY = "₹"
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
BUDGET_LEVELS = ("budget", "mid", "luxury")

# Per-day costs in rupees. "stay" is per room (2 people share a room);
# "food" and "local" (local transport) are per person.
COSTS = {
    "low":  {"budget": {"stay": 1200, "food": 500,  "local": 300},
             "mid":    {"stay": 3000, "food": 1000, "local": 700},
             "luxury": {"stay": 9000, "food": 2500, "local": 2000}},
    "high": {"budget": {"stay": 1800, "food": 700,  "local": 500},
             "mid":    {"stay": 4500, "food": 1400, "local": 1200},
             "luxury": {"stay": 14000, "food": 3500, "local": 3000}},
}

# avg_high: average daytime high in °C for Jan..Dec. rainy: monsoon months (1-12).
DESTINATIONS = [
    {"id": "goa", "name": "Goa", "state": "Goa", "types": ["beach", "nightlife"], "cost": "high",
     "summary": "Beaches, Portuguese-era churches, seafood shacks and nightlife.",
     "best_months": [11, 12, 1, 2], "rainy": [6, 7, 8, 9],
     "avg_high": [32, 32, 33, 33, 33, 30, 29, 29, 30, 32, 33, 33],
     "getting_there": "Fly into Goa (GOI or GOX), or take a train to Madgaon or Thivim.",
     "attractions": [
         {"name": "Baga & Calangute beaches", "type": "beach", "entry_fee": 0, "hours": 4, "note": "Water sports, busy shacks, best at sunset."},
         {"name": "Basilica of Bom Jesus, Old Goa", "type": "heritage", "entry_fee": 0, "hours": 2, "note": "UNESCO church, closed to tourists during mass."},
         {"name": "Fort Aguada", "type": "heritage", "entry_fee": 0, "hours": 1.5, "note": "17th-century fort and lighthouse with sea views."},
         {"name": "Dudhsagar Falls", "type": "nature", "entry_fee": 400, "hours": 6, "note": "Jeep safari to the falls. Closed during monsoon."},
         {"name": "Palolem beach, South Goa", "type": "beach", "entry_fee": 0, "hours": 5, "note": "Quieter crescent beach, kayaking, dolphin boat trips."},
         {"name": "Anjuna flea market", "type": "shopping", "entry_fee": 0, "hours": 2, "note": "Wednesdays only, Nov to Apr."},
     ]},
    {"id": "jaipur", "name": "Jaipur", "state": "Rajasthan", "types": ["heritage", "culture", "shopping"], "cost": "low",
     "summary": "The Pink City: hill forts, palaces, bazaars and Rajasthani food.",
     "best_months": [10, 11, 12, 1, 2, 3], "rainy": [7, 8],
     "avg_high": [22, 26, 32, 37, 41, 40, 35, 33, 34, 33, 28, 24],
     "getting_there": "Jaipur airport (JAI), or about 4.5 hours by train or road from Delhi.",
     "attractions": [
         {"name": "Amber Fort", "type": "heritage", "entry_fee": 200, "hours": 3, "note": "Go early to avoid crowds and heat."},
         {"name": "City Palace", "type": "heritage", "entry_fee": 300, "hours": 2, "note": "Royal residence and museum in the old city."},
         {"name": "Hawa Mahal", "type": "heritage", "entry_fee": 50, "hours": 1, "note": "Best photographed from cafes across the road in the morning."},
         {"name": "Jantar Mantar", "type": "heritage", "entry_fee": 50, "hours": 1, "note": "UNESCO astronomical instruments."},
         {"name": "Nahargarh Fort", "type": "heritage", "entry_fee": 50, "hours": 2, "note": "Sunset views over the city."},
         {"name": "Johari & Bapu Bazaar", "type": "shopping", "entry_fee": 0, "hours": 2, "note": "Jewellery, block prints, juttis. Bargain."},
     ]},
    {"id": "manali", "name": "Manali", "state": "Himachal Pradesh", "types": ["mountains", "adventure", "snow"], "cost": "low",
     "summary": "Himalayan town with pine forests, river rafting, paragliding and snow at Solang and Rohtang.",
     "best_months": [3, 4, 5, 6, 10], "rainy": [7, 8],
     "avg_high": [9, 10, 15, 20, 24, 26, 25, 24, 23, 20, 15, 11],
     "getting_there": "Overnight Volvo bus from Delhi (12-14 h), or fly to Bhuntar (KUU) and drive 1.5 h.",
     "attractions": [
         {"name": "Solang Valley", "type": "adventure", "entry_fee": 0, "hours": 5, "note": "Paragliding and ropeway in summer, skiing in winter."},
         {"name": "Rohtang Pass", "type": "nature", "entry_fee": 550, "hours": 7, "note": "Needs an online permit. Usually open May to Nov."},
         {"name": "Hadimba Temple", "type": "spiritual", "entry_fee": 0, "hours": 1, "note": "Wooden temple in a cedar forest."},
         {"name": "Old Manali", "type": "culture", "entry_fee": 0, "hours": 3, "note": "Cafes, guesthouses and the Manu Temple."},
         {"name": "River rafting, Kullu", "type": "adventure", "entry_fee": 800, "hours": 2, "note": "Beas river, roughly Apr to Jun and Sep to Oct."},
     ]},
    {"id": "alleppey", "name": "Alleppey (Kerala backwaters)", "state": "Kerala", "types": ["nature", "relaxation", "beach"], "cost": "high",
     "summary": "Houseboat cruises through palm-lined canals, Ayurvedic spas and Kerala food.",
     "best_months": [11, 12, 1, 2], "rainy": [6, 7, 8],
     "avg_high": [32, 33, 33, 33, 32, 29, 29, 29, 30, 30, 31, 31],
     "getting_there": "Fly to Kochi (COK) and drive about 1.5 hours, or take a train to Alappuzha.",
     "attractions": [
         {"name": "Overnight houseboat cruise", "type": "nature", "entry_fee": 9000, "hours": 22, "note": "Price is per boat for 2 people, meals included."},
         {"name": "Alleppey beach", "type": "beach", "entry_fee": 0, "hours": 2, "note": "Old pier and lighthouse, nice at sunset."},
         {"name": "Kayak tour of village canals", "type": "nature", "entry_fee": 800, "hours": 3, "note": "Reaches narrow canals houseboats can't."},
         {"name": "Marari beach", "type": "beach", "entry_fee": 0, "hours": 4, "note": "Quiet fishing-village beach 30 min north."},
         {"name": "Ayurvedic massage", "type": "relaxation", "entry_fee": 2000, "hours": 1.5, "note": "Book at a certified centre."},
     ]},
    {"id": "rishikesh", "name": "Rishikesh", "state": "Uttarakhand", "types": ["spiritual", "adventure", "mountains"], "cost": "low",
     "summary": "Yoga capital on the Ganga with river rafting, ashrams and the evening aarti.",
     "best_months": [2, 3, 4, 9, 10, 11], "rainy": [7, 8],
     "avg_high": [20, 23, 28, 34, 38, 38, 34, 33, 32, 30, 26, 22],
     "getting_there": "Fly to Dehradun (DED) and drive 45 min, or about 6 hours by road from Delhi.",
     "attractions": [
         {"name": "Ganga aarti at Triveni Ghat", "type": "spiritual", "entry_fee": 0, "hours": 1.5, "note": "Every evening around sunset."},
         {"name": "White-water rafting", "type": "adventure", "entry_fee": 1000, "hours": 3, "note": "Shivpuri to Rishikesh stretch. Stops during monsoon."},
         {"name": "Laxman Jhula & Ram Jhula", "type": "culture", "entry_fee": 0, "hours": 2, "note": "Suspension bridges, cafes and shops."},
         {"name": "Beatles Ashram", "type": "heritage", "entry_fee": 150, "hours": 1.5, "note": "Graffiti-covered ruins in the forest."},
         {"name": "Drop-in yoga class", "type": "spiritual", "entry_fee": 500, "hours": 1.5, "note": "Many ashrams offer morning sessions."},
     ]},
    {"id": "udaipur", "name": "Udaipur", "state": "Rajasthan", "types": ["heritage", "romantic", "culture"], "cost": "low",
     "summary": "City of Lakes: palaces on the water, rooftop dinners and sunset boat rides.",
     "best_months": [9, 10, 11, 12, 1, 2, 3], "rainy": [7, 8],
     "avg_high": [24, 28, 33, 37, 39, 36, 31, 29, 31, 33, 30, 26],
     "getting_there": "Udaipur airport (UDR), or overnight train from Delhi or Jaipur.",
     "attractions": [
         {"name": "City Palace", "type": "heritage", "entry_fee": 300, "hours": 3, "note": "Largest palace complex in Rajasthan."},
         {"name": "Lake Pichola boat ride", "type": "romantic", "entry_fee": 500, "hours": 1, "note": "Go at sunset."},
         {"name": "Bagore ki Haveli dance show", "type": "culture", "entry_fee": 150, "hours": 1, "note": "Rajasthani folk dance, 7 PM daily."},
         {"name": "Sajjangarh (Monsoon Palace)", "type": "heritage", "entry_fee": 100, "hours": 2, "note": "Hilltop palace with sunset views."},
         {"name": "Saheliyon ki Bari", "type": "nature", "entry_fee": 50, "hours": 1, "note": "Garden with fountains and lotus pools."},
     ]},
    {"id": "leh", "name": "Leh-Ladakh", "state": "Ladakh", "types": ["mountains", "adventure", "road trip"], "cost": "high",
     "summary": "High-altitude desert with monasteries, Pangong Lake and the world's highest motorable passes.",
     "best_months": [5, 6, 7, 8, 9], "rainy": [],
     "avg_high": [-2, 1, 6, 12, 16, 21, 25, 24, 20, 13, 6, 1],
     "getting_there": "Fly to Leh (IXL). Roads from Manali and Srinagar open roughly June to October.",
     "tips": "Leh is at 3,500 m. Rest fully on day 1 to acclimatise before going higher.",
     "attractions": [
         {"name": "Pangong Lake", "type": "nature", "entry_fee": 0, "hours": 10, "note": "5 h drive each way. Best as an overnight trip. Needs an inner line permit."},
         {"name": "Nubra Valley & Khardung La", "type": "adventure", "entry_fee": 0, "hours": 10, "note": "Sand dunes and double-humped camels. Overnight recommended."},
         {"name": "Thiksey Monastery", "type": "spiritual", "entry_fee": 50, "hours": 2, "note": "Attend morning prayers around 6 AM."},
         {"name": "Shanti Stupa", "type": "spiritual", "entry_fee": 0, "hours": 1, "note": "Sunset views over Leh."},
         {"name": "Leh Palace", "type": "heritage", "entry_fee": 100, "hours": 1.5, "note": "Nine-storey royal palace above the old town."},
     ]},
    {"id": "varanasi", "name": "Varanasi", "state": "Uttar Pradesh", "types": ["spiritual", "culture", "heritage"], "cost": "low",
     "summary": "One of the world's oldest living cities: ghats, boat rides at dawn and the Ganga aarti.",
     "best_months": [10, 11, 12, 1, 2, 3], "rainy": [7, 8, 9],
     "avg_high": [22, 26, 32, 38, 40, 38, 33, 32, 32, 31, 28, 23],
     "getting_there": "Varanasi airport (VNS), or train to Varanasi Junction from most big cities.",
     "attractions": [
         {"name": "Sunrise boat ride on the Ganga", "type": "spiritual", "entry_fee": 500, "hours": 1.5, "note": "Shared boats are cheaper. Start around 5:30 AM."},
         {"name": "Ganga aarti at Dashashwamedh Ghat", "type": "spiritual", "entry_fee": 0, "hours": 1.5, "note": "Arrive 45 min early for a good spot, or watch from a boat."},
         {"name": "Kashi Vishwanath Temple", "type": "spiritual", "entry_fee": 0, "hours": 2, "note": "No phones or bags inside. Use the lockers."},
         {"name": "Sarnath", "type": "heritage", "entry_fee": 25, "hours": 3, "note": "Where the Buddha gave his first sermon. 30 min away."},
         {"name": "Old city food walk", "type": "culture", "entry_fee": 0, "hours": 2, "note": "Kachori, lassi, malaiyo (winter only)."},
     ]},
]

_BY_ID = {d["id"]: d for d in DESTINATIONS}


def _month_number(month) -> int:
    """Accept 3, '3', 'march' or 'Mar'. Returns 0 for empty."""
    if not month:
        return 0
    text = str(month).strip().lower()
    if text.isdigit() and 1 <= int(text) <= 12:
        return int(text)
    for i, name in enumerate(MONTHS, start=1):
        if name.lower().startswith(text[:3]):
            return i
    raise ValueError(f"'{month}' is not a month. Use a name like 'March' or a number 1-12.")


def get_destination(destination_id: str) -> dict:
    d = _BY_ID.get((destination_id or "").strip().lower())
    if not d:
        raise ValueError(f"No destination with id '{destination_id}'. Valid ids: {', '.join(_BY_ID)}.")
    return d


def daily_cost_per_person(d: dict, level: str) -> int:
    c = COSTS[d["cost"]][level]
    return c["stay"] // 2 + c["food"] + c["local"]


def card(d: dict) -> dict:
    """Short version of a destination for lists and the website."""
    return {
        "id": d["id"], "name": d["name"], "state": d["state"], "types": d["types"],
        "summary": d["summary"],
        "best_months": [MONTHS[m - 1] for m in d["best_months"]],
        "from_per_day": daily_cost_per_person(d, "budget"),
    }


def search_destinations(query="", trip_type="", month=0, max_daily_budget=0):
    q = (query or "").lower().strip()
    t = (trip_type or "").lower().strip()
    m = _month_number(month)
    results = []
    for d in DESTINATIONS:
        text = " ".join([d["name"], d["state"], d["summary"], *d["types"]]).lower()
        if q and q not in text:
            continue
        if t and t not in d["types"]:
            continue
        if m and m not in d["best_months"]:
            continue
        if max_daily_budget and daily_cost_per_person(d, "budget") > max_daily_budget:
            continue
        results.append(card(d))
    return results


def weather(destination_id: str, month) -> dict:
    d = get_destination(destination_id)
    m = _month_number(month)
    if not m:
        raise ValueError("Please give a month.")
    high = d["avg_high"][m - 1]
    if m in d["rainy"]:
        conditions = "monsoon: frequent heavy rain, some activities closed"
    elif high >= 38:
        conditions = "very hot: plan sightseeing for early morning and evening"
    elif high <= 5:
        conditions = "freezing: heavy snow, many roads and passes closed"
    elif high <= 15:
        conditions = "cold: pack warm layers"
    else:
        conditions = "pleasant"
    return {
        "destination": d["name"], "month": MONTHS[m - 1], "avg_high_c": high,
        "conditions": conditions, "good_time_to_visit": m in d["best_months"],
        "best_months": [MONTHS[x - 1] for x in d["best_months"]],
    }


def estimate_budget(destination_id: str, days: int, travellers: int, level: str) -> dict:
    d = get_destination(destination_id)
    level = (level or "mid").lower().strip()
    if level not in BUDGET_LEVELS:
        raise ValueError(f"Budget level must be one of {', '.join(BUDGET_LEVELS)}.")
    if not 1 <= days <= 30:
        raise ValueError("Trips can be 1 to 30 days long.")
    if not 1 <= travellers <= 20:
        raise ValueError("Travellers must be between 1 and 20.")
    c = COSTS[d["cost"]][level]
    rooms = math.ceil(travellers / 2)
    nights = max(days - 1, 1)
    stay = c["stay"] * rooms * nights
    food = c["food"] * travellers * days
    local = c["local"] * travellers * days
    total = stay + food + local
    return {
        "destination": d["name"], "days": days, "nights": nights, "travellers": travellers,
        "level": level, "rooms": rooms, "currency": CURRENCY,
        "stay": stay, "food": food, "local_transport": local,
        "total": total, "per_person": round(total / travellers),
        "not_included": "Flights or trains to get there, entry fees and activities.",
    }


@dataclass
class Session:
    trips: dict = field(default_factory=dict)  # trip_id -> trip
    gemini_chat: object = None  # Gemini chat session (agent.py)
    gemini_model: str = ""  # model the chat is currently on


SESSIONS: dict[str, Session] = {}


def get_session(session_id: str) -> Session:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = Session()
    return SESSIONS[session_id]


def save_trip(session: Session, destination_id: str, days: int, travellers: int, level: str,
              start_date: str, day_plans: list[str], title: str = "") -> dict:
    d = get_destination(destination_id)
    plans = [p.strip() for p in (day_plans or []) if p and p.strip()]
    if not plans:
        raise ValueError("Add at least one day's plan before saving.")
    if len(plans) != days:
        raise ValueError(f"The trip is {days} days but has {len(plans)} day plans. They must match.")
    budget = estimate_budget(d["id"], days, travellers, level)
    trip_id = "TR" + "".join(random.choices(string.digits, k=5))
    trip = {
        "id": trip_id, "title": title.strip() or f"{days} days in {d['name']}",
        "destination_id": d["id"], "destination": d["name"],
        "start_date": start_date.strip(), "days": days, "travellers": travellers,
        "level": budget["level"], "estimated_total": budget["total"], "currency": CURRENCY,
        "day_plans": plans,
    }
    session.trips[trip_id] = trip
    return trip


def delete_trip(session: Session, trip_id: str) -> dict:
    trip = session.trips.pop((trip_id or "").strip().upper(), None)
    if not trip:
        raise ValueError(f"No saved trip with id '{trip_id}'.")
    return {"deleted": trip["id"], "title": trip["title"]}
