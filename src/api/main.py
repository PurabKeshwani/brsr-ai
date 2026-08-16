"""
FastAPI application entrypoint.

Run with:
    uvicorn api.main:app --reload --app-dir src

CORS is open in development (allow_origins=["*"]) so the Next.js dev
server (typically localhost:3000) can call this API (typically
localhost:8000) without a proxy. Tighten this to a specific origin list
before any production deployment.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from db.session import init_db

app = FastAPI(title="BRSR Greenwashing Analysis API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}