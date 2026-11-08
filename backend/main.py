from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="PayPal Shopping Agent API")

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "paypal-shopping-agent"}


# TODO: mount routers as endpoints are built
# from routers import flow_a, flow_b, flow_c, merchant, savings
# app.include_router(flow_a.router, prefix="/api")
