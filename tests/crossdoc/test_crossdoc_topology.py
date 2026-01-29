import json
from pathlib import Path

import pytest

from src.crossdoc_topology import CROSSDOC_VERSION, build_crossdoc_topology

pytestmark = pytest.mark.redflag

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "crossdoc"


def test_crossdoc_topology_snapshot(tmp_path):
    documents = {
        "docA": (FIXTURE_DIR / "doc_a.txt").read_text(encoding="utf-8"),
        "docB": (FIXTURE_DIR / "doc_b.txt").read_text(encoding="utf-8"),
    }
    payload = build_crossdoc_topology(documents)
    assert payload["version"] == CROSSDOC_VERSION
    snapshot_path = Path(__file__).resolve().parents[1] / "snapshots" / "s7" / "crossdoc_topology.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    if not snapshot_path.exists():
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload == expected


def test_crossdoc_has_no_inferred_edges():
    documents = {
        "docA": (FIXTURE_DIR / "doc_a.txt").read_text(encoding="utf-8"),
        "docB": (FIXTURE_DIR / "doc_b.txt").read_text(encoding="utf-8"),
    }
    payload = build_crossdoc_topology(documents)
    assert payload["edges"] == []  # no inference allowed
    assert payload["nodes"]  # nodes collected deterministically


def test_phrase_without_reference_emits_no_edge():
    text = (FIXTURE_DIR / "doc_a.txt").read_text(encoding="utf-8")
    payload = build_crossdoc_topology({"docA": text})
    assert payload["edges"] == []  # phrase present but no reference identities
