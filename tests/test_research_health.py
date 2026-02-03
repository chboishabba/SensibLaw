from __future__ import annotations

from collections import Counter
from datetime import date
import math
import zlib
from pathlib import Path

from src.models.document import Document, DocumentMetadata
from src.reports.research_health import compute_research_health
from src.storage.versioned_store import VersionedStore


def _make_doc(citation: str, body: str) -> Document:
    metadata = DocumentMetadata(
        jurisdiction="au",
        citation=citation,
        date=date(2024, 1, 1),
        title=citation,
    )
    return Document(metadata=metadata, body=body)


def test_research_health_counts_and_resolution(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    store = VersionedStore(db)
    try:
        doc1 = _make_doc("[1992] HCA 23", "Doc text with [1992] HCA 23 and [2000] HCA 1.")
        doc2 = _make_doc("[2000] HCA 1", "Second doc without new cites.")

        id1 = store.generate_id()
        store.add_revision(id1, doc1, doc1.metadata.date)
        id2 = store.generate_id()
        store.add_revision(id2, doc2, doc2.metadata.date)
    finally:
        store.close()

    report = compute_research_health(db)
    assert report.documents == 2
    assert report.citations_total == 2  # both citations from doc1
    assert report.citations_unresolved == 0  # both citations match stored docs
    assert report.unresolved_percent == 0.0
    assert report.citations_per_doc_mean == round(report.citations_total / report.documents, 2)
    assert report.compression_ratio_mean > 0
    assert report.tokens_per_document_mean == 7.5


def test_research_health_empty_store(tmp_path: Path) -> None:
    db = tmp_path / "empty.sqlite"
    db.touch()
    report = compute_research_health(db)
    assert report.documents == 0
    assert report.citations_total == 0
    assert report.citations_unresolved == 0
    assert report.compression_ratio_mean == 0.0
    assert report.tokens_per_document_mean == 0.0


def _block_entropy(data: bytes, block_size: int) -> float:
    if len(data) < block_size or block_size == 0:
        return 0.0
    window_count = len(data) - block_size + 1
    counts = Counter(data[i : i + block_size] for i in range(window_count))
    entropy = 0.0
    for count in counts.values():
        probability = count / window_count
        entropy -= probability * math.log2(probability)
    return entropy


def _estimate_entropy_rate(data: bytes, max_order: int = 3) -> float:
    if not data or max_order <= 0:
        return 0.0
    entropies: list[float] = []
    for k in range(1, max_order + 1):
        if len(data) < k:
            break
        entropies.append(_block_entropy(data, k))
    if not entropies:
        return 0.0
    rate_candidates: list[float] = [entropies[0]]
    for previous, current in zip(entropies, entropies[1:]):
        rate_candidates.append(max(current - previous, 0.0))
    return min(rate_candidates)


def test_research_health_compression_ratio_above_shannon_limit(tmp_path: Path) -> None:
    db = tmp_path / "shannon.sqlite"
    store = VersionedStore(db)
    bodies = [
        "abc" * 400,  # periodic / low conditional entropy
        "".join(chr(65 + (i * 37 % 26)) for i in range(1024)),  # pseudo-random pattern
    ]
    ratios: list[float] = []

    try:
        for idx, body in enumerate(bodies):
            doc = _make_doc(f"[2026] HCA {idx}", body)
            doc_id = store.generate_id()
            store.add_revision(doc_id, doc, doc.metadata.date)
            body_bytes = body.encode("utf-8")
            compressed = zlib.compress(body_bytes)
            ratios.append(len(compressed) / len(body_bytes))
    finally:
        store.close()

    report = compute_research_health(db)
    expected_mean = round(sum(ratios) / len(ratios), 2)
    assert report.documents == len(bodies)
    assert report.compression_ratio_mean == expected_mean

    for body, ratio in zip(bodies, ratios):
        body_bytes = body.encode("utf-8")
        entropy_rate_bits = _estimate_entropy_rate(body_bytes, max_order=3)
        if body_bytes:
            shannon_ratio = entropy_rate_bits / 8.0
        else:
            shannon_ratio = 0.0
        assert ratio + 1e-12 >= shannon_ratio
