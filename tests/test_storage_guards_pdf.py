from pathlib import Path

import pytest

from src.pdf_ingest import process_pdf


PDF_PATH = Path("act-2005-004.pdf")  # smaller fixture (~2.5MB) for storage guard
# Use a per-test temp DB to avoid bleed from prior ingests; keep the budget tight
# to catch runaway storage growth.
MAX_DB_DELTA = 6_000_000  # bytes
MAX_BODY_TO_PDF_RATIO = 6.0


@pytest.mark.slow
def test_db_growth_bounded(tmp_path: Path):
    if not PDF_PATH.exists():
        pytest.skip("PDF fixture not present")

    db_path = tmp_path / "store.db"
    before = db_path.stat().st_size if db_path.exists() else 0

    doc, _ = process_pdf(PDF_PATH, db_path=db_path)

    after = db_path.stat().st_size if db_path.exists() else 0
    delta = after - before
    assert delta < MAX_DB_DELTA

    pdf_size = PDF_PATH.stat().st_size
    body_bytes = len(doc.body.encode("utf-8"))
    assert body_bytes / max(1, pdf_size) < MAX_BODY_TO_PDF_RATIO
