"""Parser for Moodle 4.5 official documentation (MediaWiki HTML export)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from ...models.schemas import Document

logger = logging.getLogger(__name__)


def parse_moodle_html_file(file_path: Path) -> Document | None:
    """Parse a single Moodle documentation HTML file.

    Extracts title, content, categories, and canonical URL from
    the MediaWiki-generated HTML structure.
    """
    try:
        html = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return None

    soup = BeautifulSoup(html, "lxml")

    # Extract title
    title = _extract_title(soup)
    if not title:
        logger.debug(f"No title found in {file_path.name}, skipping")
        return None

    # Extract canonical URL and derive slug
    canonical_url, slug = _extract_url_and_slug(soup, file_path)

    # Extract categories
    categories = _extract_categories(soup)

    # Extract main content text
    text = _extract_content(soup)
    if not text or len(text.strip()) < 50:
        logger.debug(f"Insufficient content in {file_path.name}, skipping")
        return None

    return Document(
        source="moodle_docs",
        title=title,
        text=text,
        slug=slug,
        canonical_url=canonical_url,
        categories=categories,
        file_hash=file_path.stem,
    )


def _extract_title(soup: BeautifulSoup) -> str | None:
    """Extract document title from the heading or title tag."""
    # Primary: h1#firstHeading > span.mw-page-title-main
    h1 = soup.find("h1", id="firstHeading")
    if h1:
        span = h1.find("span", class_="mw-page-title-main")
        if span:
            return span.get_text(strip=True)
        return h1.get_text(strip=True)

    # Fallback: <title> tag, strip " - MoodleDocs" suffix
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        title_text = re.sub(r"\s*-\s*MoodleDocs\s*$", "", title_text)
        if title_text:
            return title_text

    return None


def _extract_url_and_slug(soup: BeautifulSoup, file_path: Path) -> tuple[str | None, str]:
    """Extract canonical URL and derive a human-readable slug."""
    canonical_url = None
    slug = file_path.stem  # fallback to hash

    link = soup.find("link", rel="canonical")
    if link and link.get("href"):
        canonical_url = link["href"]
        # Derive slug from URL path: https://docs.moodle.org/en/Page_name -> Page_name
        parts = canonical_url.rstrip("/").split("/")
        if parts:
            slug = parts[-1]

    return canonical_url, slug


def _extract_categories(soup: BeautifulSoup) -> list[str]:
    """Extract category names from the catlinks div."""
    categories = []
    catlinks = soup.find("div", id="catlinks")
    if catlinks:
        for a_tag in catlinks.find_all("a"):
            title = a_tag.get("title", "")
            if title.startswith("Category:"):
                cat_name = title.replace("Category:", "").strip()
                if cat_name:
                    categories.append(cat_name)
    return categories


def _extract_content(soup: BeautifulSoup) -> str:
    """Extract the main content text, stripping MediaWiki boilerplate."""
    # Find the main content div
    content_div = soup.find("div", class_="mw-parser-output")
    if not content_div:
        # Fallback: try the body content area
        content_div = soup.find("div", id="mw-content-text")
        if not content_div:
            return ""

    # Remove elements we don't want in the text
    for element in content_div.find_all(["script", "style", "noscript"]):
        element.decompose()

    # Remove table of contents (it's just navigation)
    for toc in content_div.find_all("div", id="toc"):
        toc.decompose()
    for toc in content_div.find_all("div", class_="toc"):
        toc.decompose()

    # Remove edit section links
    for edit_link in content_div.find_all("span", class_="mw-editsection"):
        edit_link.decompose()

    # Get text with paragraph separation
    text = content_div.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    # Remove parser cache comments that sometimes appear as text
    text = re.sub(r"NewPP limit report.*$", "", text, flags=re.DOTALL)
    text = re.sub(r"Transclusion expansion time report.*$", "", text, flags=re.DOTALL)

    return text.strip()


def parse_moodle_docs(docs_dir: Path) -> list[Document]:
    """Parse all Moodle documentation HTML files in the given directory.

    Recursively scans for .html files, skipping non-content files.
    """
    documents = []
    html_files = list(docs_dir.rglob("*.html"))
    logger.info(f"Found {len(html_files)} HTML files in {docs_dir}")

    skipped = 0
    for file_path in html_files:
        # Skip image directories and resource files
        if "images_en" in str(file_path) or "resources" in str(file_path):
            skipped += 1
            continue

        doc = parse_moodle_html_file(file_path)
        if doc:
            documents.append(doc)
        else:
            skipped += 1

    logger.info(
        f"Parsed {len(documents)} Moodle docs, skipped {skipped} files"
    )
    return documents
