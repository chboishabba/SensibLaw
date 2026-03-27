from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Tuple

from src.sources.austlii_sino import SinoQuery
from src.sources.austlii_sino_parse import AustLiiSearchHit, parse_sino_search_html
from src.sources.base import FetchResult
from src.sources.search_selection import select_search_hit
from src.pdf_ingest import process_pdf


def _select_hit(
    hits: list[AustLiiSearchHit],
    *,
    strategy: str = "first",
    mnc: str | None = None,
    index: int = 0,
    path_contains: str | None = None,
) -> tuple[AustLiiSearchHit, str]:
    return select_search_hit(
        hits,
        strategy=strategy,
        mnc=mnc,
        index=index,
        path_contains=path_contains,
    )


def search_and_fetch(
    *,
    query: str,
    vc: str,
    search_adapter,
    fetch_adapter,
    parser: Callable[[str], list[AustLiiSearchHit]] = parse_sino_search_html,
    strategy: str = "first",
    mnc: str | None = None,
    index: int = 0,
    path_contains: str | None = None,
) -> Tuple[FetchResult, AustLiiSearchHit, str]:
    """Run SINO search, select a hit deterministically, fetch its content."""

    html = search_adapter.search(SinoQuery(meta=vc, query=query))
    hits = parser(html)
    hit, reason = _select_hit(
        hits,
        strategy=strategy,
        mnc=mnc,
        index=index,
        path_contains=path_contains,
    )
    fetched = fetch_adapter.fetch(hit.url)
    return fetched, hit, reason


def ingest_pdf_from_search(
    *,
    query: str,
    vc: str,
    db_path: Path,
    search_adapter,
    fetch_adapter,
    temp_dir: Path | None = None,
    strategy: str = "first",
    mnc: str | None = None,
    index: int = 0,
    path_contains: str | None = None,
) -> Tuple[object, int | None]:
    """Search → select → fetch → ingest PDF into VersionedStore.

    - Requires the fetched content to be a PDF (content-type or .pdf URL).
    - Returns (Document, stored_doc_id).
    """

    fetched, _hit, _reason = search_and_fetch(
        query=query,
        vc=vc,
        search_adapter=search_adapter,
        fetch_adapter=fetch_adapter,
        strategy=strategy,
        mnc=mnc,
        index=index,
        path_contains=path_contains,
    )
    content_type = (fetched.content_type or "").lower()
    if "pdf" not in content_type and not fetched.url.lower().endswith(".pdf"):
        raise ValueError("Fetched content is not a PDF")

    with tempfile.NamedTemporaryFile(
        suffix=".pdf", dir=temp_dir, delete=False
    ) as tmp:
        tmp.write(fetched.content)
        pdf_path = Path(tmp.name)

    doc, stored_id = process_pdf(pdf_path, db_path=db_path)
    return doc, stored_id
