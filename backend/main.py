"""FastAPI entry point for the PayPal Shopping Agent backend.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="PayPal Shopping Agent API", version="0.1.0")

# Comma-separated list in .env; defaults to the Vite dev server.
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Liveness check (also used by the UptimeRobot keep-alive on Render)."""
    return {
        "status": "ok",
        "service": "paypal-shopping-agent",
        "paypal_env": "sandbox",
        "paypal_configured": bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_SECRET")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_MODEL")),
    }


@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs", "health": "/health"}


# Routers get mounted here in Step 2 once API.md paths are confirmed, e.g.:
# from routers import buyer, agent_pass, orders, merchant
# app.include_router(buyer.router)
