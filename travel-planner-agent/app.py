"""Web server: serves the travel planner website and the chat API.

Run:  python -m uvicorn app:app --reload   then open http://127.0.0.1:8000
"""

from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from google.genai import errors
from pydantic import BaseModel, Field

# Read GEMINI_API_KEY from the .env file next to this script.
load_dotenv(Path(__file__).parent / ".env", override=True)

import agent
import store

app = FastAPI(title="Wanderly Travel Planner Agent")
STATIC = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


def trips_of(session: store.Session) -> list:
    return list(session.trips.values())


@app.get("/")
def home():
    # no-store: always send the latest page, so an old cached copy never shows up
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/destinations")
def destinations():
    return {"currency": store.CURRENCY, "items": [store.card(d) for d in store.DESTINATIONS]}


@app.get("/api/trips/{session_id}")
def trips(session_id: str):
    return trips_of(store.get_session(session_id))


@app.delete("/api/trips/{session_id}/{trip_id}")
def delete_trip(session_id: str, trip_id: str):
    try:
        store.delete_trip(store.get_session(session_id), trip_id)
    except ValueError as err:
        raise HTTPException(404, str(err))
    return trips_of(store.get_session(session_id))


@app.post("/api/chat")
def chat(req: ChatRequest):
    session = store.get_session(req.session_id)
    try:
        reply = agent.chat(session, req.message)
    except ValueError as err:
        if "API key" not in str(err):
            raise
        raise HTTPException(500, "The AI assistant isn't configured. Paste your key into the .env file and restart the server.")
    except errors.ClientError as err:
        if err.code == 429:
            raise HTTPException(429, "The assistant is busy right now. Please try again in a moment.")
        if err.code in (400, 401, 403) and "API key" in str(err):
            raise HTTPException(500, "The Gemini API key is invalid. Check the key in the .env file and restart the server.")
        raise HTTPException(502, f"AI service error ({err.code}): {err.message}")
    except errors.ServerError as err:
        raise HTTPException(503, f"Gemini is having trouble ({err.code}). Please try again.")
    except httpx.HTTPError:
        raise HTTPException(503, "Couldn't reach the AI service. Check your internet connection.")
    return {"reply": reply, "trips": trips_of(session)}


@app.post("/api/reset/{session_id}")
def reset(session_id: str):
    """Start a new conversation but keep saved trips."""
    session = store.get_session(session_id)
    session.gemini_chat = None
    session.gemini_model = ""
    return {"ok": True}
