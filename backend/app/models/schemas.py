"""Pydantic models for API requests and responses."""

from typing import List, Optional

from pydantic import BaseModel


class Document(BaseModel):
    """A parsed document before chunking."""
    source: str  # moodle_docs, olproduction, trubox, tru_faq
    title: str
    text: str
    slug: str = ""
    canonical_url: Optional[str] = None
    categories: List[str] = []
    author: Optional[str] = None
    date_modified: Optional[str] = None
    file_hash: Optional[str] = None  # for moodle docs: the hash filename


class Chunk(BaseModel):
    """A chunk of text ready for embedding."""
    id: str  # {source}::{slug}::chunk_{index}
    text: str
    source: str
    title: str
    slug: str = ""
    canonical_url: Optional[str] = None
    categories: str = ""  # comma-separated (ChromaDB needs primitives)
    chunk_index: int = 0
    total_chunks: int = 1
    author: Optional[str] = None
    date_modified: Optional[str] = None


class SearchResult(BaseModel):
    """A single search result."""
    text: str
    score: float
    source: str
    title: str
    categories: List[str]
    canonical_url: Optional[str] = None
    chunk_index: int = 0
    total_chunks: int = 1


class SearchResponse(BaseModel):
    """Response from the search endpoint."""
    query: str
    results: List[SearchResult]
    total: int


class SourceStats(BaseModel):
    """Statistics for an ingested source."""
    source: str
    document_count: int
    chunk_count: int


class SourcesResponse(BaseModel):
    """Response from the sources endpoint."""
    sources: List[SourceStats]
    total_chunks: int


class IngestResponse(BaseModel):
    """Response from the ingest endpoint."""
    status: str
    sources_ingested: List[str]
    total_documents: int
    total_chunks: int
    duration_seconds: float
