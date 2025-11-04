import json
import logging
import sys
from pathlib import Path
from typing import Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.parser import emit_document, emit_document_from_json
from src.ingestion.consent_gate import ConsentError, SUMMARY_NOTE


def sample_record(
    *,
    storage_consent: bool = False,
    inference_consent: bool = False,
    flags: Optional[list[str]] = None,
    consent_required: bool = False,
):
    record = {
        "metadata": {
            "jurisdiction": "US",
            "citation": "123",
            "date": "2020-01-01",
        },
        "body": "example body",
        "cultural_flags": flags if flags is not None else ["sacred_data"],
    }
    if consent_required:
        record["consent_required"] = True
    if storage_consent:
        record["storage_consent"] = True
    if inference_consent:
        record["inference_consent"] = True
    if storage_consent and inference_consent:
        record["consent_receipt"] = "rcpt-001"
    return record


def test_sacred_without_consent_summarised(caplog):
    record = sample_record()
    with caplog.at_level(logging.WARNING):
        doc = emit_document(record)
    assert doc.body == SUMMARY_NOTE
    assert "Consent receipt" not in caplog.text
    assert record["cultural_flags"] == ["SACRED_DATA"]
    assert doc.metadata.cultural_flags == ["SACRED_DATA"]


def test_log_and_allow_with_consent(caplog):
    record = sample_record(storage_consent=True, inference_consent=True)
    with caplog.at_level(logging.INFO):
        doc = emit_document(record)
    assert doc.body == "example body"
    assert "Consent receipt" in caplog.text
    assert record["cultural_flags"] == ["SACRED_DATA"]
    assert doc.metadata.cultural_flags == ["SACRED_DATA"]


def test_from_json_summarises_without_consent(caplog):
    record = sample_record()
    data = json.dumps(record)
    with caplog.at_level(logging.WARNING):
        doc = emit_document_from_json(data)
    assert doc.body == SUMMARY_NOTE
    assert "Consent receipt" not in caplog.text
    assert doc.metadata.cultural_flags == ["SACRED_DATA"]


def test_consent_required_field_blocks():
    record = sample_record(flags=[], consent_required=True)
    with pytest.raises(ConsentError):
        emit_document(record)


def test_consent_required_allows_with_consent(caplog):
    record = sample_record(
        storage_consent=True,
        inference_consent=True,
        flags=[],
        consent_required=True,
    )
    with caplog.at_level(logging.INFO):
        doc = emit_document(record)
    assert doc.body == "example body"
    assert "Consent receipt" in caplog.text


def test_alias_flags_canonicalised():
    record = sample_record(flags=["pii"])
    doc = emit_document(record)
    assert record["cultural_flags"] == [
        "PERSONALLY_IDENTIFIABLE_INFORMATION"
    ]
    assert doc.metadata.cultural_flags == [
        "PERSONALLY_IDENTIFIABLE_INFORMATION"
    ]
