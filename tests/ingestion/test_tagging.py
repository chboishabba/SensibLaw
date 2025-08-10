import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.parser import emit_document


def test_australian_tagging():
    record = {
        "metadata": {
            "jurisdiction": "Australia",
            "citation": "ABC123",
            "date": "2023-01-01",
        },
        "body": "The law promotes fair treatment and environmental protection.",
    }
    doc = emit_document(record)
    assert "AU" in doc.metadata.jurisdiction_codes
    tags = doc.metadata.ontology_tags
    assert "lpo" in tags and "fairness" in tags["lpo"]
    assert "environment" in tags and "conservation" in tags["environment"]
