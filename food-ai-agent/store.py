"""Menu data, carts, and orders for the demo restaurant.

Everything lives in memory so the project runs with no database.
Swap these functions for real DB calls when you connect your own site.
"""

import random
import string
import time
from dataclasses import dataclass, field

RESTAURANT = {
    "name": "Spice Garden",
    "hours": "11:00 AM - 11:00 PM, every day",
    "delivery_fee": 40,
    "free_delivery_above": 499,
    "tax_rate": 0.05,  # 5% GST
    "currency": "₹",
}

MENU = [
    # id, name, category, price, veg, spice (0-3), description, tags
    {"id": "S1", "name": "Paneer Tikka", "category": "Starters", "price": 249, "veg": True, "spice": 2,
     "description": "Cottage cheese cubes marinated in yogurt and spices, grilled in a tandoor.", "tags": ["grilled", "bestseller"]},
    {"id": "S2", "name": "Chicken 65", "category": "Starters", "price": 279, "veg": False, "spice": 3,
     "description": "Crispy deep-fried chicken tossed with curry leaves and red chillies.", "tags": ["fried", "spicy"]},
    {"id": "S3", "name": "Veg Spring Rolls", "category": "Starters", "price": 179, "veg": True, "spice": 0,
     "description": "Crispy rolls stuffed with cabbage, carrot and glass noodles.", "tags": ["fried", "kids"]},
    {"id": "M1", "name": "Butter Chicken", "category": "Mains", "price": 349, "veg": False, "spice": 1,
     "description": "Tandoori chicken in a rich, creamy tomato-butter gravy.", "tags": ["creamy", "bestseller"]},
    {"id": "M2", "name": "Dal Makhani", "category": "Mains", "price": 229, "veg": True, "spice": 1,
     "description": "Black lentils slow-cooked overnight with butter and cream.", "tags": ["creamy"]},
    {"id": "M3", "name": "Palak Paneer", "category": "Mains", "price": 259, "veg": True, "spice": 1,
     "description": "Cottage cheese in a smooth spinach gravy.", "tags": ["healthy"]},
    {"id": "M4", "name": "Hyderabadi Chicken Biryani", "category": "Mains", "price": 329, "veg": False, "spice": 2,
     "description": "Dum-cooked basmati rice layered with spiced chicken. Served with raita.", "tags": ["rice", "bestseller"]},
    {"id": "M5", "name": "Veg Biryani", "category": "Mains", "price": 269, "veg": True, "spice": 2,
     "description": "Fragrant basmati rice with mixed vegetables and whole spices.", "tags": ["rice"]},
    {"id": "M6", "name": "Masala Dosa", "category": "Mains", "price": 149, "veg": True, "spice": 1,
     "description": "Crispy rice crepe filled with spiced potato, with sambar and chutney.", "tags": ["south indian", "vegan"]},
    {"id": "B1", "name": "Butter Naan", "category": "Breads", "price": 59, "veg": True, "spice": 0,
     "description": "Soft tandoor-baked bread brushed with butter.", "tags": []},
    {"id": "B2", "name": "Garlic Naan", "category": "Breads", "price": 69, "veg": True, "spice": 0,
     "description": "Naan topped with garlic and coriander.", "tags": []},
    {"id": "B3", "name": "Tandoori Roti", "category": "Breads", "price": 39, "veg": True, "spice": 0,
     "description": "Whole-wheat bread from the tandoor.", "tags": ["vegan"]},
    {"id": "D1", "name": "Gulab Jamun (2 pcs)", "category": "Desserts", "price": 99, "veg": True, "spice": 0,
     "description": "Warm milk dumplings soaked in rose-cardamom syrup.", "tags": ["sweet"]},
    {"id": "D2", "name": "Mango Kulfi", "category": "Desserts", "price": 119, "veg": True, "spice": 0,
     "description": "Traditional Indian ice cream made with Alphonso mango.", "tags": ["cold"]},
    {"id": "K1", "name": "Mango Lassi", "category": "Drinks", "price": 109, "veg": True, "spice": 0,
     "description": "Chilled yogurt drink blended with mango.", "tags": ["cold"]},
    {"id": "K2", "name": "Masala Chai", "category": "Drinks", "price": 49, "veg": True, "spice": 0,
     "description": "Spiced milk tea.", "tags": ["hot"]},
    {"id": "K3", "name": "Fresh Lime Soda", "category": "Drinks", "price": 79, "veg": True, "spice": 0,
     "description": "Sweet or salted, made fresh.", "tags": ["cold", "vegan"]},
]

MENU_BY_ID = {item["id"]: item for item in MENU}


@dataclass
class Session:
    cart: dict = field(default_factory=dict)  # item_id -> {"qty": int, "notes": str}
    messages: list = field(default_factory=list)  # Claude conversation history (agent_claude.py)
    gemini_chat: object = None  # Gemini chat session (agent.py)
    gemini_model: str = ""  # model the chat is currently on


SESSIONS: dict[str, Session] = {}
ORDERS: dict[str, dict] = {}


def get_session(session_id: str) -> Session:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = Session()
    return SESSIONS[session_id]


def search_menu(query="", category="", veg_only=False, max_price=None, max_spice=None):
    q = (query or "").lower().strip()
    results = []
    for item in MENU:
        text = " ".join([item["name"], item["description"], item["category"], *item["tags"]]).lower()
        if q and not all(word in text for word in q.split()):
            continue
        if category and item["category"].lower() != category.lower():
            continue
        if veg_only and not item["veg"]:
            continue
        if max_price is not None and item["price"] > max_price:
            continue
        if max_spice is not None and item["spice"] > max_spice:
            continue
        results.append(item)
    return results


def cart_summary(session: Session) -> dict:
    lines, subtotal = [], 0
    for item_id, entry in session.cart.items():
        item = MENU_BY_ID[item_id]
        line_total = item["price"] * entry["qty"]
        subtotal += line_total
        lines.append({"id": item_id, "name": item["name"], "qty": entry["qty"],
                      "price": item["price"], "line_total": line_total, "notes": entry["notes"]})
    delivery = 0 if subtotal == 0 or subtotal >= RESTAURANT["free_delivery_above"] else RESTAURANT["delivery_fee"]
    tax = round(subtotal * RESTAURANT["tax_rate"])
    return {"items": lines, "subtotal": subtotal, "tax": tax,
            "delivery_fee": delivery, "total": subtotal + tax + delivery}


def add_to_cart(session: Session, item_id: str, quantity: int = 1, notes: str = ""):
    item_id = item_id.upper()
    if item_id not in MENU_BY_ID:
        raise ValueError(f"No menu item with id '{item_id}'. Use search_menu to find valid ids.")
    if not 1 <= quantity <= 20:
        raise ValueError("Quantity must be between 1 and 20.")
    entry = session.cart.setdefault(item_id, {"qty": 0, "notes": ""})
    entry["qty"] += quantity
    if notes:
        entry["notes"] = notes
    return cart_summary(session)


def update_cart_item(session: Session, item_id: str, quantity: int):
    item_id = item_id.upper()
    if item_id not in session.cart:
        raise ValueError(f"'{item_id}' is not in the cart.")
    if quantity <= 0:
        del session.cart[item_id]
    else:
        session.cart[item_id]["qty"] = quantity
    return cart_summary(session)


def place_order(session: Session, customer_name: str, phone: str, address: str, payment_method: str):
    summary = cart_summary(session)
    if not summary["items"]:
        raise ValueError("The cart is empty.")
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        raise ValueError("Phone number looks invalid; ask the customer for a 10-digit number.")
    if payment_method not in ("cash", "upi", "card"):
        raise ValueError("payment_method must be cash, upi or card.")
    order_id = "SG" + "".join(random.choices(string.digits, k=6))
    ORDERS[order_id] = {
        "order_id": order_id, "customer_name": customer_name, "phone": digits, "address": address,
        "payment_method": payment_method, **summary, "placed_at": time.time(),
    }
    session.cart.clear()
    return {"order_id": order_id, "total": summary["total"], "eta_minutes": 35}


def track_order(order_id: str):
    order = ORDERS.get(order_id.upper())
    if not order:
        raise ValueError(f"No order found with id '{order_id}'.")
    minutes = (time.time() - order["placed_at"]) / 60
    # Simulated progress so the demo shows something useful.
    if minutes < 2:
        status = "Order received"
    elif minutes < 10:
        status = "Being prepared in the kitchen"
    elif minutes < 25:
        status = "Out for delivery"
    else:
        status = "Delivered"
    return {"order_id": order["order_id"], "status": status, "total": order["total"],
            "items": [f'{l["qty"]} x {l["name"]}' for l in order["items"]]}
