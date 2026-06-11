"""Moodle Support Companion — FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import search, sources, ingest, conversation, cases, questions
from .cases.database import init_database
from .config import FRONTEND_DIST

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Moodle Support Companion",
    description="Diagnostic support tool for TRU Learning Technology & Innovation",
    version="0.3.0",
)

# CORS — allow the React dev server (local dev only; production serves from same origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(sources.router, prefix="/api", tags=["sources"])
app.include_router(ingest.router, prefix="/api", tags=["ingest"])
app.include_router(conversation.router, prefix="/api", tags=["conversation"])
app.include_router(cases.router, prefix="/api", tags=["cases"])
app.include_router(questions.router, prefix="/api", tags=["questions"])


@app.on_event("startup")
async def startup():
    init_database()
    from .conversation.session_store import init_store, cleanup_expired
    init_store()
    cleanup_expired()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve the built React frontend in production
# This must come AFTER all API routes so /api/* paths are handled first
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    # Serve other static files in the root (favicon, logo, etc.)
    @app.get("/lti-logo.png")
    async def logo():
        return FileResponse(str(FRONTEND_DIST / "lti-logo.png"))

    @app.get("/favicon.svg")
    async def favicon():
        return FileResponse(str(FRONTEND_DIST / "favicon.svg"))

    # Catch-all: serve index.html for any non-API route (SPA routing)
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        # If the file exists in dist, serve it
        file_path = FRONTEND_DIST / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html (SPA client-side routing)
        return FileResponse(str(FRONTEND_DIST / "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "name": "Moodle Support Companion",
            "version": "0.3.0",
            "status": "running",
            "docs": "/docs",
            "note": "Frontend not built. Run 'npm run build' in the frontend/ directory.",
        }
