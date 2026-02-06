import pytest
from datetime import date

from src.crossdoc_topology import build_crossdoc_topology
from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom, RuleReference

pytestmark = pytest.mark.redflag


def _doc(body: str, refs: list[RuleReference], source_id: str) -> Document:
    meta = DocumentMetadata(jurisdiction="NSW", citation="CIT", date=date(2024, 1, 1), provenance=source_id)
    prov = Provision(text=body, rule_atoms=[RuleAtom(references=refs)])
    return Document(metadata=meta, body=body, provisions=[prov])


@pytest.mark.parametrize(
    "phrase",
    [
        "conflict with",
        "overrides",
        "prevails over",
        "controls",
        "conflicts with",
    ],
)
def test_forbidden_phrases_never_emit_edges(phrase):
    body = f"This clause, {phrase} section 2 of the Other Act, must be followed."
    ref = RuleReference(work="Other Act", section="2", provenance={"clause_id": "docA-clause-0"})
    documents = {"docA": _doc(body, [ref], source_id="docA")}

    payload = build_crossdoc_topology(documents)

    assert payload["edges"] == []  # forbidden phrases gate emission
