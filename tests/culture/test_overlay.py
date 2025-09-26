from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.pdf_ingest import build_document


def make_pages(text: str) -> list[dict]:
    return [{"heading": "Section 1", "text": text}]


def test_redaction_overlay_applies_to_body_and_provisions():
    pages = make_pages("Sensitive text")
    document = build_document(pages, Path("dummy.pdf"), cultural_flags=["SACRED_DATA"])

    expected = "[REDACTED: SACRED_DATA]"
    assert document.body == expected
    assert all(provision.text == expected for provision in document.provisions)
    assert "SACRED_DATA" in document.metadata.cultural_redactions
    assert document.metadata.cultural_consent_required is True


def test_hash_transform_applied_with_annotations():
    pages = make_pages("Personal data")
    document = build_document(
        pages,
        Path("dummy.pdf"),
        cultural_flags=["PERSONALLY_IDENTIFIABLE_INFORMATION"],
    )

    original_body = "Section 1\nPersonal data"
    expected_hash = hashlib.sha256(original_body.encode("utf-8")).hexdigest()
    assert document.body == expected_hash
    assert all(provision.text == expected_hash for provision in document.provisions)
    assert document.metadata.cultural_consent_required is True
    annotations = document.metadata.cultural_annotations
    assert any(
        annotation.startswith(
            "PERSONALLY_IDENTIFIABLE_INFORMATION: redaction=none, consent_required=True"
        )
        for annotation in annotations
    )


def test_public_domain_flag_records_annotation_without_consent():
    pages = make_pages("General text")
    document = build_document(pages, Path("dummy.pdf"), cultural_flags=["PUBLIC_DOMAIN"])

    assert document.body == "Section 1\nGeneral text"
    assert document.metadata.cultural_consent_required is False
    assert any(
        annotation.startswith("PUBLIC_DOMAIN: redaction=none, consent_required=False")
        for annotation in document.metadata.cultural_annotations
    )
