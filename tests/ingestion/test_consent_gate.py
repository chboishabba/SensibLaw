import json
import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.parser import emit_document, emit_document_from_json
from src.ingestion.consent_gate import ConsentError


def sample_record(consent: bool = False):
    record = {
        "metadata": {
            "jurisdiction": "US",
            "citation": "123",
            "date": "2020-01-01",
        },
        "body": "example body",
        "cultural_flags": ["restricted"],
    }
    if consent:
        record.update({"consent": True, "consent_receipt": "rcpt-001"})
    return record


def test_block_without_consent():
    record = sample_record(consent=False)
    with pytest.raises(ConsentError):
        emit_document(record)


def test_log_and_allow_with_consent(caplog):
    record = sample_record(consent=True)
    with caplog.at_level(logging.INFO):
        doc = emit_document(record)
    assert doc.body == "example body"
    assert "Consent receipt" in caplog.text


def test_from_json_enforces_policy():
    record = sample_record(consent=False)
    data = json.dumps(record)
    with pytest.raises(ConsentError):
        emit_document_from_json(data)
