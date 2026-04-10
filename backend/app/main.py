"""Moodle Support Companion — FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import search, sources, ingest, conversation, cases
from .cases.database import init_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Moodle Support Companion",
    description="Diagnostic support tool for TRU Learning Technology & Innovation",
    version="0.2.0",
)

# CORS — allow the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(sources.router, prefix="/api", tags=["sources"])
app.include_router(ingest.router, prefix="/api", tags=["ingest"])
app.include_router(conversation.router, prefix="/api", tags=["conversation"])
app.include_router(cases.router, prefix="/api", tags=["cases"])


@app.on_event("startup")
async def startup():
    init_database()


@app.get("/")
async def root():
    return {
        "name": "Moodle Support Companion",
        "version": "0.2.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
