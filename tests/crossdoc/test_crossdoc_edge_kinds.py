from datetime import date
from pathlib import Path

import pytest

from src.crossdoc_topology import build_crossdoc_topology
from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom, RuleReference
from src.obligation_identity import compute_identities
from src.obligations import extract_obligations_from_document

pytestmark = pytest.mark.redflag


def _doc(body: str, refs: list[RuleReference], source_id: str) -> Document:
    meta = DocumentMetadata(jurisdiction="NSW", citation="CIT", date=date(2024, 1, 1), provenance=source_id)
    prov = Provision(text=body, rule_atoms=[RuleAtom(references=refs)])
    return Document(metadata=meta, body=body, provisions=[prov])


@pytest.mark.parametrize(
    "kind, body, ref_work, ref_section",
    [
        (
            "conflicts_with",
            "This clause must apply to the extent of any inconsistency with section 5 of the Old Act.",
            "Old Act",
            "5",
        ),
        (
            "exception_to",
            "Except as provided in section 3 of the Carveout Act, this section must apply.",
            "Carveout Act",
            "3",
        ),
        (
            "applies_despite",
            "Despite section 7 of the Override Act, this section must apply.",
            "Override Act",
            "7",
        ),
        (
            "applies_subject_to",
            "Subject to section 9 of the Base Act, the operator must notify.",
            "Base Act",
            "9",
        ),
    ],
)
def test_edge_kinds_positive(kind, body, ref_work, ref_section):
    ref_src = RuleReference(work=ref_work, section=ref_section, provenance={"clause_id": "doc-new-clause-0"})
    ref_tgt = RuleReference(work=ref_work, section=ref_section, provenance={"clause_id": "doc-old-clause-0"})

    documents = {
        "doc-new": _doc(body, [ref_src], source_id="doc-new"),
        "doc-old": _doc("Section 1 must apply to all operators.", [ref_tgt], source_id="doc-old"),
    }
    payload = build_crossdoc_topology(documents)

    assert payload["edges"], f"{kind} edge should be emitted"
    edge = payload["edges"][0]
    assert edge["kind"] == kind
    assert edge["provenance"]["source_id"] == "doc-new"
    assert edge["provenance"]["clause_id"].startswith("doc-new-clause-")


@pytest.mark.parametrize(
    "body",
    [
        "This clause applies to the extent of any inconsistency with section 5 of the Old Act.",
        "Except as provided in section 3 of the Carveout Act, this section applies.",
        "Despite section 7 of the Override Act, this section applies.",
        "Subject to section 9 of the Base Act, the operator must notify.",
    ],
)
def test_edge_requires_reference_identity(body):
    documents = {"doc-new": _doc(body, [], source_id="doc-new")}
    payload = build_crossdoc_topology(documents)
    assert payload["edges"] == []  # phrase present but no reference to resolve


def test_topology_does_not_mutate_obligation_identities():
    ref = RuleReference(work="Old Act", section="1", provenance={"clause_id": "doc-new-clause-0"})
    doc = _doc("The minister must supersede section 1 of the Old Act.", [ref], source_id="doc-new")

    obligations_before = extract_obligations_from_document(doc)
    ids_before = {oid.identity_hash for oid in compute_identities(obligations_before)}

    _ = build_crossdoc_topology({"doc-new": doc})

    obligations_after = extract_obligations_from_document(doc)
    ids_after = {oid.identity_hash for oid in compute_identities(obligations_after)}

    assert ids_before == ids_after
