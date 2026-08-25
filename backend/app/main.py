"""Moodle Support Companion — FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import search, sources, ingest, conversation, cases, questions, activities
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
app.include_router(activities.router, prefix="/api", tags=["activities"])


def _seed_knowledge_base() -> None:
    """Seed the runtime vector store from the prebuilt index baked into the image.

    The index is embedded at build time (see Dockerfile) at a fixed path that
    differs from the runtime data dir (the Railway volume mount). If the live
    store is empty, copy the prebuilt index into place so the knowledge base is
    ready without any runtime embedding. Runs before the vector-store client is
    first created (on the first search), so the client reads the seeded files.
    """
    import shutil
    from .config import CHROMA_DB_PATH, PREBUILT_CHROMA_DIR

    log = logging.getLogger("app.startup")
    if not PREBUILT_CHROMA_DIR.exists():
        return  # no prebuilt index (e.g. local dev) — nothing to seed

    # Treat the live store as populated only if its sqlite is non-trivial. An
    # empty Chroma db is ~150 KB; a populated one (thousands of chunks) is many MB.
    sqlite = CHROMA_DB_PATH / "chroma.sqlite3"
    if sqlite.exists() and sqlite.stat().st_size > 1_000_000:
        log.info("Knowledge base already populated — skipping seed")
        return

    try:
        if CHROMA_DB_PATH.exists():
            shutil.rmtree(CHROMA_DB_PATH)
        CHROMA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PREBUILT_CHROMA_DIR, CHROMA_DB_PATH)
        log.info(f"Seeded knowledge base from prebuilt index into {CHROMA_DB_PATH}")
    except Exception as e:  # noqa: BLE001 — never block startup on seeding
        log.error(f"Failed to seed knowledge base from prebuilt index: {e}")


@app.on_event("startup")
async def startup():
    _seed_knowledge_base()
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
