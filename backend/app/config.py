"""Configuration for the Moodle Support Companion."""

from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # moodle-support-companion/../
DATA_DIR = Path(__file__).parent.parent.parent / "data"
CHROMA_DB_PATH = DATA_DIR / "chroma_db"

# Knowledge source paths (relative to the Moodle Help folder)
MOODLE_HELP_DIR = PROJECT_ROOT  # The "Moodle Help" folder
MOODLE_DOCS_DIR = MOODLE_HELP_DIR / "moodledocs_en" / "405" / "en"
OL_PRODUCTION_XML = MOODLE_HELP_DIR / "olproduction.WordPress.2026-04-07.xml"
TRUBOX_XML = MOODLE_HELP_DIR / "trubox.WordPress.2026-04-07.xml"
TRU_FAQ_DOCX = MOODLE_HELP_DIR / "TRU Moodle FAQ.docx"

# Chunking settings
CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200  # characters
MIN_CHUNK_SIZE = 100  # skip chunks smaller than this
SINGLE_CHUNK_THRESHOLD = 1500  # docs smaller than this stay as one chunk

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# ChromaDB
COLLECTION_NAME = "moodle_knowledge"

# Search defaults
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50

# Claude API (conversation)
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 4096
MAX_CONTEXT_CHUNKS = 5  # KB results to inject per message
MAX_CONVERSATION_TURNS = 50

# Case tracking
CASE_DB_PATH = DATA_DIR / "cases.db"

# .mbz uploads
MBZ_UPLOAD_DIR = DATA_DIR / "mbz_uploads"
