import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.api.sample_routes import api_provision, api_subgraph, api_treatment


def test_subgraph_endpoint():
    data = api_subgraph("example text")
    assert "cloud" in data
    assert "tokens" in data
    assert data["tokens"], "expected at least one token"
    first = data["tokens"][0]
    assert {"text", "lemma_", "pos_", "morph", "idx", "class_"}.issubset(first)
    assert first["class_"] is None


def test_treatment_endpoint():
    data = api_treatment("a person shall act")
    assert "rules" in data


def test_provision_endpoint():
    data = api_provision("Sample provision text")
    assert "provision" in data

