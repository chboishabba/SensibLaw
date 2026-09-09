from __future__ import annotations

import hashlib
from pathlib import Path

from src.ontology.wikidata_nat_source_media_materialization import (
    materialize_source_fetch_dispatch,
    materialize_source_fetch_receipt,
)
from src.ontology.wikidata_nat_source_support import fetch_source_content


class _Response:
    def __init__(self, body: bytes, *, content_type: str = "text/html") -> None:
        self.status_code = 200
        self.headers = {"Content-Type": content_type}
        self.url = "https://example.test/report"
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 65536):
        del chunk_size
        yield self._body


def _public(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.ontology.wikidata_nat_source_support._public_http_url",
        lambda url: (True, "public_http_origin"),
    )


def test_fetch_persists_body_by_digest_and_materializes_html(tmp_path, monkeypatch) -> None:
    _public(monkeypatch)
    body = b"<html><body><h1>Report</h1><p>Scope 1 emissions 1082 in 2024.</p></body></html>"
    artifact_dir = tmp_path / "artifacts"
    receipt = fetch_source_content(
        {"fetch_ref": "fetch:1", "url": "https://example.test/report"},
        http_get=lambda *args, **kwargs: _Response(body),
        artifact_store_dir=artifact_dir,
    )

    digest_hex = hashlib.sha256(body).hexdigest()
    assert receipt["content_digest"] == f"sha256:{digest_hex}"
    assert receipt["artifact_persisted"] is True
    assert receipt["artifact_relpath"] == f"sha256/{digest_hex[:2]}/{digest_hex}.bin"
    assert (artifact_dir / receipt["artifact_relpath"]).read_bytes() == body
    assert receipt["source_support_paid"] is False

    materialized_dir = tmp_path / "materialized"
    result = materialize_source_fetch_receipt(
        receipt,
        artifact_store_dir=artifact_dir,
        materialized_store_dir=materialized_dir,
    )
    assert result["state"] == "materialized"
    assert result["media_kind"] == "html"
    assert result["source_bytes_reverified"] is True
    assert result["canonical_text_created"] is True
    assert result["canonical_char_count"] > 0
    assert result["proposition_support_evaluated"] is False
    assert result["authority_evaluated"] is False
    assert (materialized_dir / result["canonical_text_relpath"]).exists()


def test_materializer_rejects_store_tampering(tmp_path, monkeypatch) -> None:
    _public(monkeypatch)
    body = b"<html><body>stable</body></html>"
    artifact_dir = tmp_path / "artifacts"
    receipt = fetch_source_content(
        {"fetch_ref": "fetch:2", "url": "https://example.test/report"},
        http_get=lambda *args, **kwargs: _Response(body),
        artifact_store_dir=artifact_dir,
    )
    (artifact_dir / receipt["artifact_relpath"]).write_bytes(b"tampered")

    try:
        materialize_source_fetch_receipt(
            receipt,
            artifact_store_dir=artifact_dir,
            materialized_store_dir=tmp_path / "materialized",
        )
    except ValueError as exc:
        assert "no longer matches fetch receipt" in str(exc)
    else:
        raise AssertionError("tampered content-addressed source artifact was accepted")


def test_dispatch_materializes_unique_fetch_receipts_only(tmp_path, monkeypatch) -> None:
    _public(monkeypatch)
    artifact_dir = tmp_path / "artifacts"
    body = b"<html><body>one canonical source for many consumers</body></html>"
    receipt = fetch_source_content(
        {"fetch_ref": "fetch:3", "url": "https://example.test/report"},
        http_get=lambda *args, **kwargs: _Response(body),
        artifact_store_dir=artifact_dir,
    )
    dispatch = materialize_source_fetch_dispatch(
        {
            "dispatch_ref": "dispatch:source",
            "fetch_receipts": [receipt],
        },
        artifact_store_dir=artifact_dir,
        materialized_store_dir=tmp_path / "materialized",
    )
    assert dispatch["source_fetch_receipt_count"] == 1
    assert dispatch["materialization_count"] == 1
    assert dispatch["materialized_source_count"] == 1
    assert dispatch["proposition_support_evaluated"] is False
    assert dispatch["semantic_promotion_performed"] is False


def test_pdf_path_reuses_existing_pdf_page_adapter(tmp_path, monkeypatch) -> None:
    _public(monkeypatch)
    body = b"%PDF synthetic fixture bytes"
    artifact_dir = tmp_path / "artifacts"
    receipt = fetch_source_content(
        {"fetch_ref": "fetch:4", "url": "https://example.test/report.pdf"},
        http_get=lambda *args, **kwargs: _Response(body, content_type="application/pdf"),
        artifact_store_dir=artifact_dir,
    )
    monkeypatch.setattr(
        "src.ontology.wikidata_nat_source_media_materialization._pdf_page_records",
        lambda value: [{"page": 1, "heading": "", "text": "Scope 1 emissions 1082 in 2024"}],
    )
    result = materialize_source_fetch_receipt(
        receipt,
        artifact_store_dir=artifact_dir,
        materialized_store_dir=tmp_path / "materialized",
    )
    assert result["state"] == "materialized"
    assert result["media_kind"] == "pdf"
    assert result["page_count"] == 1
    assert result["canonical_segment_count"] == 1
    assert result["proposition_support_evaluated"] is False
