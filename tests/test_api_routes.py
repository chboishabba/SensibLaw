import sys
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.sample_routes import api_provision, api_subgraph, api_treatment


def test_subgraph_endpoint():
    data = api_subgraph(["doc1", "doc2"], limit=10, offset=0)
    assert len(data["nodes"]) == 2
    assert any(e["target"] == "doc2" for e in data["edges"])


def test_treatment_endpoint():
    data = api_treatment(doc="doc1", limit=10, offset=0)
    assert any(e["target"] == "doc2" for e in data["treatments"])


def test_provision_endpoint():
    data = api_provision(doc="doc1", id="prov1")
    assert data["identifier"] == "prov1"
