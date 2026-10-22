"""Web server: serves the food website and the chat API.

Run:  python -m uvicorn app:app --reload   then open http://127.0.0.1:8000
"""

from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from google.genai import errors
from pydantic import BaseModel, Field

# Read GEMINI_API_KEY from the .env file next to this script. override=True makes
# the file win over any old key left in the terminal (e.g. from $env:GEMINI_API_KEY).
load_dotenv(Path(__file__).parent / ".env", override=True)

import agent
import store

app = FastAPI(title="Spice Garden AI Agent")
STATIC = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/menu")
def menu():
    return {"restaurant": store.RESTAURANT, "items": store.MENU}


@app.get("/api/cart/{session_id}")
def cart(session_id: str):
    return store.cart_summary(store.get_session(session_id))


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
    return {"reply": reply, "cart": store.cart_summary(session)}


@app.post("/api/reset/{session_id}")
def reset(session_id: str):
    store.SESSIONS.pop(session_id, None)
    return {"ok": True}
