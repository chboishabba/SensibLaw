from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from src.citations.normalize import CitationKey, normalize_mnc
from src.ingestion.citation_follow import extract_citations
from src.models.document import DocumentMetadata
from src.storage.versioned_store import VersionedStore
from src.text.tokenize_simple import count_tokens


@dataclass(frozen=True)
class ResearchHealth:
    documents: int
    citations_total: int
    citations_per_doc_mean: float
    citations_unresolved: int
    unresolved_percent: float
    max_citation_depth: int
    db_size_mb: float
    db_delta_mb_per_doc_mean: float
    compression_ratio_mean: float
    tokens_per_document_mean: float

    def to_dict(self) -> dict:
        return {
            "documents": self.documents,
            "citations_total": self.citations_total,
            "citations_per_doc_mean": self.citations_per_doc_mean,
            "citations_unresolved": self.citations_unresolved,
            "unresolved_percent": self.unresolved_percent,
            "max_citation_depth": self.max_citation_depth,
            "db_size_mb": self.db_size_mb,
            "db_delta_mb_per_doc_mean": self.db_delta_mb_per_doc_mean,
            "compression_ratio_mean": self.compression_ratio_mean,
            "tokens_per_document_mean": self.tokens_per_document_mean,
        }


def _latest_revisions(store: VersionedStore) -> Iterable[tuple[int, str, str]]:
    """Yield (doc_id, metadata_json, body) for the latest revision of each document."""
    rows = store.conn.execute(
        """
        SELECT r.doc_id, r.metadata, r.body
        FROM revisions r
        JOIN (
            SELECT doc_id, MAX(rev_id) AS rev_id
            FROM revisions
            GROUP BY doc_id
        ) latest ON r.doc_id = latest.doc_id AND r.rev_id = latest.rev_id
        ORDER BY r.doc_id
        """
    ).fetchall()
    for row in rows:
        yield int(row["doc_id"]), row["metadata"], row["body"] or ""


def _metadata_citation_keys(rows: Iterable[tuple[int, str, str]]) -> set[CitationKey]:
    keys: set[CitationKey] = set()
    for _, metadata_json, _ in rows:
        metadata = DocumentMetadata.from_dict(json.loads(metadata_json))
        if metadata.citation:
            key = normalize_mnc(str(metadata.citation))
            if key:
                keys.add(key)
    return keys


def compute_research_health(db_path: Path) -> ResearchHealth:
    """Compute high-level corpus health metrics for the given SQLite store.

    Pure function: no network, no side effects; returns deterministic, rounded metrics.
    """

    store = VersionedStore(db_path)
    try:
        rows = list(_latest_revisions(store))
    finally:
        store.close()

    doc_count = len(rows)
    size_mb = round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0.0

    if doc_count == 0:
        return ResearchHealth(
            documents=0,
            citations_total=0,
            citations_per_doc_mean=0.0,
            citations_unresolved=0,
            unresolved_percent=0.0,
            max_citation_depth=0,
            db_size_mb=size_mb,
            db_delta_mb_per_doc_mean=0.0,
            compression_ratio_mean=0.0,
            tokens_per_document_mean=0.0,
        )

    # Build a map of existing documents by citation for simple resolution.
    citation_keys = _metadata_citation_keys(rows)

    citations_total = 0
    citations_unresolved = 0
    token_totals = 0
    compression_ratios: list[float] = []

    for _, metadata_json, body in rows:
        refs = extract_citations(body)
        citations_total += len(refs)
        token_totals += count_tokens(body)

        body_bytes = body.encode("utf-8")
        if body_bytes:
            compressed = zlib.compress(body_bytes)
            if len(body_bytes) > 0:
                compression_ratios.append(len(compressed) / len(body_bytes))

        for ref in refs:
            if ref.key and ref.key in citation_keys:
                continue
            citations_unresolved += 1

    citations_per_doc_mean = round(citations_total / doc_count, 2) if doc_count else 0.0
    unresolved_percent = round((citations_unresolved / citations_total * 100), 2) if citations_total else 0.0
    db_delta_mb_per_doc_mean = round(size_mb / doc_count, 2) if doc_count else 0.0
    compression_ratio_mean = round(
        (sum(compression_ratios) / len(compression_ratios)) if compression_ratios else 0.0, 2
    )
    tokens_per_document_mean = round((token_totals / doc_count), 2) if doc_count else 0.0

    # Depth tracking isn’t persisted; report 0 when none, otherwise the minimal informative value.
    max_citation_depth = 1 if citations_total else 0

    return ResearchHealth(
        documents=doc_count,
        citations_total=citations_total,
        citations_per_doc_mean=citations_per_doc_mean,
        citations_unresolved=citations_unresolved,
        unresolved_percent=unresolved_percent,
        max_citation_depth=max_citation_depth,
        db_size_mb=size_mb,
        db_delta_mb_per_doc_mean=db_delta_mb_per_doc_mean,
        compression_ratio_mean=compression_ratio_mean,
        tokens_per_document_mean=tokens_per_document_mean,
    )
