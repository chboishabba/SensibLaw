from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pytest

from src.pdf_ingest import process_pdf
from src.text.tokenize_simple import count_tokens


pdfminer = pytest.importorskip("pdfminer.high_level")


ROOT = Path(__file__).resolve().parents[1]

CORPUS_FIXTURES = [
    ROOT / "Mabo [No 2] - [1992] HCA 23.pdf",
    ROOT / "1936 HCA House v. The King.pdf",
    ROOT / "Plaintiff S157_2002 v Commonwealth - [2003] HCA 2.pdf",
    ROOT / "Native Title (New South Wales) Act 1994 (NSW).pdf",
]


def _body_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _missing_textspan_warnings(records: list[logging.LogRecord]) -> list[str]:
    out: list[str] = []
    for record in records:
        if record.name != "src.pdf_ingest":
            continue
        message = record.getMessage()
        if "missing TextSpan for rule atom text" in message:
            out.append(message)
        if "missing TextSpan for rule element" in message:
            out.append(message)
    return out


@pytest.mark.parametrize("pdf_path", CORPUS_FIXTURES, ids=lambda p: p.stem)
def test_pdf_fixture_ingest_has_no_textspan_warnings(
    pdf_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    if not pdf_path.exists():
        pytest.skip(f"PDF fixture missing: {pdf_path.name}")

    out_path = tmp_path / f"{pdf_path.stem}.json"
    with caplog.at_level(logging.WARNING, logger="src.pdf_ingest"):
        doc, stored_id = process_pdf(pdf_path, output=out_path, db_path=None)

    assert stored_id is None
    assert doc.body.strip(), f"Expected non-empty body for {pdf_path.name}"
    assert getattr(doc, "provisions", None), f"Expected provisions for {pdf_path.name}"
    assert doc.metadata.compression_stats, f"Expected compression stats for {pdf_path.name}"
    assert not _missing_textspan_warnings(caplog.records), (
        f"Unexpected TextSpan warnings for {pdf_path.name}: "
        f"{_missing_textspan_warnings(caplog.records)}"
    )


@pytest.mark.parametrize("pdf_path", CORPUS_FIXTURES, ids=lambda p: p.stem)
def test_pdf_fixture_ingest_is_deterministic_for_same_bytes(
    pdf_path: Path, tmp_path: Path
) -> None:
    if not pdf_path.exists():
        pytest.skip(f"PDF fixture missing: {pdf_path.name}")

    out_a = tmp_path / f"{pdf_path.stem}.run_a.json"
    out_b = tmp_path / f"{pdf_path.stem}.run_b.json"

    doc_a, _ = process_pdf(pdf_path, output=out_a, db_path=None)
    doc_b, _ = process_pdf(pdf_path, output=out_b, db_path=None)

    assert _body_hash(doc_a.body) == _body_hash(doc_b.body)
    assert count_tokens(doc_a.body) == count_tokens(doc_b.body)
    assert doc_a.metadata.compression_stats == doc_b.metadata.compression_stats
    assert len(doc_a.provisions or []) == len(doc_b.provisions or [])
