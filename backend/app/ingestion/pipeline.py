"""Ingestion pipeline: parse all sources, chunk, and store in vector DB."""

import logging
import time

from ..config import MOODLE_DOCS_DIR, OL_PRODUCTION_XML, TRUBOX_XML, TRU_FAQ_DOCX
from ..models.schemas import Document
from ..search.vector_store import reset_collection, add_chunks
from .parsers.moodle_html import parse_moodle_docs
from .parsers.wordpress_xml import parse_wordpress_xml
from .parsers.docx_parser import parse_docx
from .chunker import chunk_documents

logger = logging.getLogger(__name__)


def run_ingestion() -> dict:
    """Run the full ingestion pipeline.

    Parses all knowledge sources, chunks them, and stores in ChromaDB.
    Returns statistics about the ingestion run.
    """
    start_time = time.time()
    all_documents: list[Document] = []
    sources_ingested = []

    # 1. Parse Moodle documentation
    if MOODLE_DOCS_DIR.exists():
        logger.info(f"Parsing Moodle docs from {MOODLE_DOCS_DIR}")
        moodle_docs = parse_moodle_docs(MOODLE_DOCS_DIR)
        all_documents.extend(moodle_docs)
        sources_ingested.append("moodle_docs")
        logger.info(f"  → {len(moodle_docs)} Moodle documents")
    else:
        logger.warning(f"Moodle docs directory not found: {MOODLE_DOCS_DIR}")

    # 2. Parse OL Production WordPress export
    if OL_PRODUCTION_XML.exists():
        logger.info(f"Parsing OL Production from {OL_PRODUCTION_XML.name}")
        ol_docs = parse_wordpress_xml(
            OL_PRODUCTION_XML,
            source_name="olproduction",
            post_types=["docs"],
        )
        all_documents.extend(ol_docs)
        sources_ingested.append("olproduction")
        logger.info(f"  → {len(ol_docs)} OL Production documents")
    else:
        logger.warning(f"OL Production XML not found: {OL_PRODUCTION_XML}")

    # 3. Parse TRU Box / Orientation WordPress export
    if TRUBOX_XML.exists():
        logger.info(f"Parsing TRU Box from {TRUBOX_XML.name}")
        trubox_docs = parse_wordpress_xml(
            TRUBOX_XML,
            source_name="trubox",
            post_types=["post", "page"],
        )
        all_documents.extend(trubox_docs)
        sources_ingested.append("trubox")
        logger.info(f"  → {len(trubox_docs)} TRU Box documents")
    else:
        logger.warning(f"TRU Box XML not found: {TRUBOX_XML}")

    # 4. Parse TRU Moodle FAQ
    if TRU_FAQ_DOCX.exists():
        logger.info(f"Parsing TRU FAQ from {TRU_FAQ_DOCX.name}")
        faq_docs = parse_docx(TRU_FAQ_DOCX, source_name="tru_faq")
        all_documents.extend(faq_docs)
        sources_ingested.append("tru_faq")
        logger.info(f"  → {len(faq_docs)} FAQ sections")
    else:
        logger.warning(f"TRU FAQ not found: {TRU_FAQ_DOCX}")

    logger.info(f"Total documents parsed: {len(all_documents)}")

    # 5. Chunk all documents
    logger.info("Chunking documents...")
    all_chunks = chunk_documents(all_documents)
    logger.info(f"Total chunks created: {len(all_chunks)}")

    # 6. Reset and populate vector store
    logger.info("Resetting vector store and ingesting chunks...")
    reset_collection()
    add_chunks(all_chunks)

    duration = time.time() - start_time
    stats = {
        "status": "completed",
        "sources_ingested": sources_ingested,
        "total_documents": len(all_documents),
        "total_chunks": len(all_chunks),
        "duration_seconds": round(duration, 2),
    }

    logger.info(
        f"Ingestion complete in {duration:.1f}s: "
        f"{len(all_documents)} docs → {len(all_chunks)} chunks"
    )
    return stats


if __name__ == "__main__":
    # Allow running directly: python -m app.ingestion.pipeline
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stats = run_ingestion()
    print(f"\nIngestion complete:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
