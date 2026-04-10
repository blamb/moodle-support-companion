"""Parser for WordPress WXR (WordPress eXtended RSS) XML exports."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from bs4 import BeautifulSoup

from ...models.schemas import Document

logger = logging.getLogger(__name__)

# WordPress WXR namespace map
WXR_NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
}


def _get_text(element: ET.Element | None, xpath: str, namespaces: dict) -> str:
    """Safely extract text from an XML element."""
    if element is None:
        return ""
    child = element.find(xpath, namespaces)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _clean_wordpress_content(html_content: str) -> str:
    """Strip WordPress block comments and convert HTML to plain text."""
    if not html_content:
        return ""

    # Strip Gutenberg block comments: <!-- wp:paragraph -->, <!-- /wp:heading -->, etc.
    text = re.sub(r"<!--\s*/?wp:\w+[^>]*-->", "", html_content)

    # Strip remaining HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Parse remaining HTML to extract text
    soup = BeautifulSoup(text, "lxml")

    # Remove script/style elements
    for element in soup.find_all(["script", "style"]):
        element.decompose()

    # Get clean text
    clean = soup.get_text(separator="\n", strip=True)

    # Clean up whitespace
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = re.sub(r"[ \t]+", " ", clean)

    return clean.strip()


def _extract_categories(item: ET.Element) -> list[str]:
    """Extract category names from an item element."""
    categories = []
    for cat in item.findall("category"):
        domain = cat.get("domain", "")
        if domain in ("doc_category", "category"):
            cat_text = cat.text
            if cat_text:
                # Strip leading numbers like "3. " from category names
                cat_name = re.sub(r"^\d+\.\s*", "", cat_text.strip())
                categories.append(cat_name)
    return categories


def parse_wordpress_xml(
    xml_path: Path,
    source_name: str,
    post_types: list[str] | None = None,
) -> list[Document]:
    """Parse a WordPress WXR XML export file.

    Args:
        xml_path: Path to the XML file
        source_name: Source identifier (e.g., "olproduction", "trubox")
        post_types: List of post types to include. Defaults to ["docs", "post", "page"].
    """
    if post_types is None:
        post_types = ["docs", "post", "page"]

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        logger.error(f"Failed to parse XML {xml_path}: {e}")
        return []

    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        logger.error(f"No channel element in {xml_path}")
        return []

    # Get site URL for building canonical URLs
    site_link = ""
    link_el = channel.find("link")
    if link_el is not None and link_el.text:
        site_link = link_el.text.rstrip("/")

    documents = []
    items = channel.findall("item")
    logger.info(f"Found {len(items)} items in {xml_path.name}")

    for item in items:
        post_type = _get_text(item, "wp:post_type", WXR_NS)
        status = _get_text(item, "wp:status", WXR_NS)

        # Filter by post type and published status
        if post_type not in post_types:
            continue
        if status != "publish":
            continue

        title = ""
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            title = title_el.text.strip()

        if not title:
            continue

        # Extract content
        content_raw = _get_text(item, "content:encoded", WXR_NS)
        text = _clean_wordpress_content(content_raw)

        if not text or len(text) < 30:
            continue

        # Extract metadata
        slug = _get_text(item, "wp:post_name", WXR_NS)
        author = _get_text(item, "dc:creator", WXR_NS)
        date_modified = _get_text(item, "wp:post_modified", WXR_NS)
        categories = _extract_categories(item)

        # Build canonical URL
        canonical_url = None
        link_el = item.find("link")
        if link_el is not None and link_el.text:
            canonical_url = link_el.text.strip()
        elif slug and site_link:
            canonical_url = f"{site_link}/{slug}/"

        documents.append(Document(
            source=source_name,
            title=title,
            text=text,
            slug=slug,
            canonical_url=canonical_url,
            categories=categories,
            author=author,
            date_modified=date_modified,
        ))

    logger.info(f"Parsed {len(documents)} documents from {xml_path.name}")
    return documents
