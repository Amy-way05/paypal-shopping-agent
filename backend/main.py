"""FastAPI entry point for the PayPal Shopping Agent backend.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000
"""
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from routers import agent, agent_pass, buyer, demo, merchant, orders  # noqa: E402
from services import llm, models_adapter, paypal_client  # noqa: E402

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app):
    # data/ and *.joblib are gitignored: build them on first start, then warm the caches.
    models_adapter.ensure_ready()
    models_adapter.warm_up()
    yield


app = FastAPI(title="PayPal Shopping Agent API", version="0.3.0", lifespan=lifespan,
              description="Contract: API.md v0.3. Data from models/ (synthetic), payments via PayPal Sandbox.")

# Comma-separated list in .env; defaults to the Vite dev server.
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """API.md says bad input is 400 BAD_REQUEST (FastAPI's default is 422)."""
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    first = errors[0] if errors else {"field": "", "message": "Invalid request"}
    return JSONResponse(status_code=400, content={"detail": {
        "code": "BAD_REQUEST", "message": f"{first['field']}: {first['message']}".strip(": "), "errors": errors}})


@app.get("/health", tags=["Health"])
def health():
    """Liveness check (also used by the UptimeRobot keep-alive on Render)."""
    return {
        "status": "ok",
        "service": "paypal-shopping-agent",
        "paypal_env": "sandbox",
        "paypal_configured": paypal_client.enabled(),
        "gemini_configured": llm.enabled(),
        "gemini_models": llm.models() if llm.enabled() else [],
        "data_as_of": models_adapter.DATA_TODAY.isoformat(),
    }


@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "docs": "/docs", "health": "/health"}


for r in (buyer, agent_pass, orders, merchant, agent, demo):
    app.include_router(r.router)
