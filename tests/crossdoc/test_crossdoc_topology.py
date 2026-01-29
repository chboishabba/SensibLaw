import json
from datetime import date
from pathlib import Path

import pytest
import jsonschema
import yaml

from src.crossdoc_topology import CROSSDOC_VERSION, build_crossdoc_topology
from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom, RuleReference

pytestmark = pytest.mark.redflag

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "crossdoc"


def _doc(body: str, refs: list[RuleReference], source_id: str) -> Document:
    meta = DocumentMetadata(jurisdiction="NSW", citation="CIT", date=date(2024, 1, 1), provenance=source_id)
    prov = Provision(text=body, rule_atoms=[RuleAtom(references=refs)])
    return Document(metadata=meta, body=body, provisions=[prov])


def test_crossdoc_topology_snapshot(tmp_path):
    # doc-new supersedes Old Act s1; doc-old holds the referenced clause.
    body_new = "The minister must supersede section 1 of the Old Act."
    ref = RuleReference(work="Old Act", section="1", provenance={"clause_id": "doc-new-clause-0"})
    body_old = "Section 1 must apply to all operators."
    ref_old = RuleReference(work="Old Act", section="1", provenance={"clause_id": "doc-old-clause-0"})

    documents = {
        "doc-new": _doc(body_new, [ref], source_id="doc-new"),
        "doc-old": _doc(body_old, [ref_old], source_id="doc-old"),
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


def test_supersedes_edge_requires_reference_identity():
    body_new = "The minister must supersede section 1 of the Old Act."
    ref = RuleReference(work="Old Act", section="1", provenance={"clause_id": "doc-new-clause-0"})
    body_old = "Section 1 applies to all operators."
    ref_old = RuleReference(work="Old Act", section="1", provenance={"clause_id": "doc-old-clause-0"})
    doc_new = _doc(body_new, [ref], source_id="doc-new")
    doc_old = _doc(body_old, [ref_old], source_id="doc-old")

    payload = build_crossdoc_topology({"doc-new": doc_new, "doc-old": doc_old})

    # One edge emitted (kind supersedes) with required provenance fields.
    assert len(payload["edges"]) == 1
    edge = payload["edges"][0]
    assert edge["kind"] == "supersedes"
    assert edge["provenance"]["source_id"] == "doc-new"
    assert edge["provenance"]["clause_id"].startswith("doc-new-clause-")


def test_crossdoc_schema_compliance():
    schema_path = Path("sensiblaw/schemas/obligation.crossdoc.v1.schema.yaml")
    schema = yaml.safe_load(schema_path.read_text())
    payload = json.loads(Path("tests/snapshots/s7/crossdoc_topology.json").read_text())
    jsonschema.validate(payload, schema)
