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

# Knowledge source paths (relative to the Moodle Help folder)
# On Railway, these are in the repo under backend/knowledge_sources/
KNOWLEDGE_DIR = BACKEND_ROOT / "knowledge_sources"
MOODLE_HELP_DIR = PROJECT_ROOT  # The "Moodle Help" folder (local dev)
MOODLE_DOCS_DIR = MOODLE_HELP_DIR / "moodledocs_en" / "405" / "en"
OL_PRODUCTION_XML = MOODLE_HELP_DIR / "olproduction.WordPress.2026-04-07.xml"
TRUBOX_XML = MOODLE_HELP_DIR / "trubox.WordPress.2026-04-07.xml"
TRU_FAQ_DOCX = MOODLE_HELP_DIR / "TRU Moodle FAQ.docx"

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
