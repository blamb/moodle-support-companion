"""Configuration for the Moodle Support Companion."""

import os
from pathlib import Path

# Project paths — support both local dev and Railway deployment
# On Railway, RAILWAY_VOLUME_MOUNT_PATH points to persistent storage
_RAILWAY_DATA = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # moodle-support-companion/../
BACKEND_ROOT = Path(__file__).parent.parent  # backend/

if _RAILWAY_DATA:
    # Railway: use persistent volume for data
    DATA_DIR = Path(_RAILWAY_DATA)
else:
    # Local dev: use local data directory
    DATA_DIR = BACKEND_ROOT.parent / "data"

CHROMA_DB_PATH = DATA_DIR / "chroma_db"

# The Moodle release TRU's instance is running. Everything that needs to name
# a version — the system prompt, tool descriptions, the documentation export we
# ingest, the docs.moodle.org links we hand out — derives from this one value.
MOODLE_VERSION = os.environ.get("MOODLE_VERSION", "5.2")


def _docs_version_code(version: str) -> str:
    """Convert a release like "5.2" into the docs.moodle.org path code "502"."""
    major, _, minor = version.partition(".")
    try:
        return f"{int(major) * 100 + int(minor or 0):03d}"
    except ValueError:
        return version.replace(".", "")


MOODLE_DOCS_VERSION = _docs_version_code(MOODLE_VERSION)  # e.g. "502"
# Canonical URLs in the export are unversioned (docs.moodle.org/en/Page), which
# always resolves to whatever release is current upstream. Rewrite them to the
# versioned path so links stay pinned to the release TRU actually runs.
MOODLE_DOCS_BASE_URL = f"https://docs.moodle.org/{MOODLE_DOCS_VERSION}/en"

# Knowledge source paths (relative to the Moodle Help folder)
# On Railway, these are in the repo under backend/knowledge_sources/
KNOWLEDGE_DIR = BACKEND_ROOT / "knowledge_sources"
MOODLE_HELP_DIR = PROJECT_ROOT  # The "Moodle Help" folder (local dev)
_DOCS_SEARCH_ROOTS = (BACKEND_ROOT.parent, KNOWLEDGE_DIR, MOODLE_HELP_DIR)


def _resolve_moodle_docs_dir() -> Path:
    """Locate the MoodleDocs HTML export for the configured version.

    Looks for `moodledocs_en/<version code>/en` next to the repo, in the
    Railway knowledge_sources dir, and in the parent "Moodle Help" folder.
    Falls back to the highest version code present so an export dropped in
    for a newer release is picked up without a code change. MOODLE_DOCS_DIR
    in the environment overrides all of it.
    """
    override = os.environ.get("MOODLE_DOCS_DIR")
    if override:
        return Path(override)

    for root in _DOCS_SEARCH_ROOTS:
        exact = root / "moodledocs_en" / MOODLE_DOCS_VERSION / "en"
        if exact.is_dir():
            return exact

    newest = None
    for root in _DOCS_SEARCH_ROOTS:
        export = root / "moodledocs_en"
        if not export.is_dir():
            continue
        for candidate in export.iterdir():
            if (candidate / "en").is_dir() and candidate.name.isdigit():
                if newest is None or candidate.name > newest.name:
                    newest = candidate
    if newest is not None:
        return newest / "en"

    # Nothing on disk — return the expected path so the caller logs a clear miss.
    return BACKEND_ROOT.parent / "moodledocs_en" / MOODLE_DOCS_VERSION / "en"


MOODLE_DOCS_DIR = _resolve_moodle_docs_dir()
def _resolve_source_file(filename: str) -> Path:
    """Locate a single knowledge source file.

    Prefers the copy committed under backend/knowledge_sources/ (the one that
    ships in the container) and falls back to the parent "Moodle Help" folder
    for local dev. Returns the knowledge_sources path when neither exists so
    the pipeline logs a clear miss.
    """
    for root in (KNOWLEDGE_DIR, MOODLE_HELP_DIR):
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return KNOWLEDGE_DIR / filename


OL_PRODUCTION_XML = _resolve_source_file("olproduction.WordPress.2026-04-07.xml")
TRUBOX_XML = _resolve_source_file("trubox.WordPress.2026-04-07.xml")
TRU_FAQ_DOCX = _resolve_source_file("TRU Moodle FAQ.docx")

# Static frontend build (for production serving)
FRONTEND_DIST = BACKEND_ROOT.parent / "frontend" / "dist"

# Chunking settings
CHUNK_SIZE = 1500  # characters (larger to keep procedures intact)
CHUNK_OVERLAP = 300  # characters
MIN_CHUNK_SIZE = 100  # skip chunks smaller than this
SINGLE_CHUNK_THRESHOLD = 2000  # docs smaller than this stay as one chunk

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# ChromaDB
COLLECTION_NAME = "moodle_knowledge"

# Search defaults
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50

# Claude API (conversation)
# Default is Haiku for cost; set CLAUDE_MODEL=claude-sonnet-4-6 (or any other
# model alias) in the environment to upgrade without code changes.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")
CLAUDE_MAX_TOKENS = 4096
MAX_CONTEXT_CHUNKS = 5  # KB results returned per knowledge-base tool call
MAX_TOOL_ITERATIONS = 6  # cap on tool-use rounds within a single reply
MAX_CONVERSATION_TURNS = 50

# Case tracking
CASE_DB_PATH = DATA_DIR / "cases.db"

# Conversation session persistence
SESSION_DB_PATH = DATA_DIR / "sessions.db"
SESSION_TTL = 7 * 24 * 3600  # sessions survive restarts; expire after 7 days

# .mbz uploads
MBZ_UPLOAD_DIR = DATA_DIR / "mbz_uploads"
