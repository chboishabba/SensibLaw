from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from datetime import date

from src.culture.overlay import CulturalOverlay
from src.models.document import Document, DocumentMetadata
from src.models.provision import Atom, Provision
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
    assert all(len(provision.text) == 64 for provision in document.provisions)
    assert all("Personal data" not in provision.text for provision in document.provisions)
    assert document.metadata.cultural_consent_required is True
    for provision in document.provisions:
        assert all(len(principle) == 64 for principle in provision.principles)
        assert all(
            principle != "Personal data" for principle in provision.principles
        )
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


def test_hash_transform_sanitises_provision_metadata():
    overlay = CulturalOverlay.from_yaml(ROOT / "data" / "cultural_rules.yaml")
    metadata = DocumentMetadata(
        jurisdiction="",
        citation="",
        date=date.today(),
        cultural_flags=["PERSONALLY_IDENTIFIABLE_INFORMATION"],
    )
    provision = Provision(
        text="Sensitive provision",
        principles=["Sensitive principle"],
        atoms=[
            Atom(
                text="Sensitive atom",
                who="Alice",
                conditions="Only sometimes",
                refs=["ref"],
            )
        ],
    )
    document = Document(metadata=metadata, body="Sensitive provision", provisions=[provision])

    overlay.apply(document)

    hashed_body = hashlib.sha256("Sensitive provision".encode("utf-8")).hexdigest()
    assert document.body == hashed_body

    hashed_principle = hashlib.sha256("Sensitive principle".encode("utf-8")).hexdigest()
    assert document.provisions[0].principles == [hashed_principle]

    atom = document.provisions[0].atoms[0]
    assert atom.text == hashlib.sha256("Sensitive atom".encode("utf-8")).hexdigest()
    assert atom.who == hashlib.sha256("Alice".encode("utf-8")).hexdigest()
    assert atom.conditions == hashlib.sha256("Only sometimes".encode("utf-8")).hexdigest()
    assert atom.refs == [hashlib.sha256("ref".encode("utf-8")).hexdigest()]
