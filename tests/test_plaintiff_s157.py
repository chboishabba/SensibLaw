from datetime import date

import pytest

from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom
from src.obligations import extract_obligations_from_document
from src.obligation_identity import compute_identities

pytestmark = pytest.mark.redflag


def _doc_from_text(text: str, source_id: str) -> Document:
    meta = DocumentMetadata(
        jurisdiction="HCA",
        citation="Plaintiff S157/2002 v Commonwealth (2003)",
        date=date(2003, 2, 4),
        provenance=source_id,
    )
    prov = Provision(text=text, rule_atoms=[RuleAtom(references=[])])
    return Document(metadata=meta, body=text, provisions=[prov])


def test_plaintiff_s157_obligations_extract():
    """
    Guard: judgment with explicit relief/orders still yields descriptive obligations only.
    """
    text = (
        "The Court orders that the decision be quashed. "
        "The Commonwealth must not act upon the impugned decision. "
        "Relief is granted accordingly."
    )
    doc = _doc_from_text(text, source_id="plaintiff-s157")

    obligations = extract_obligations_from_document(doc)
    assert obligations, "Expected obligations to extract from operative language"


def test_plaintiff_s157_identity_stability():
    """
    Guard: identity hashes must be stable and unaffected by review/topology.
    """
    text = "The Commonwealth must not act upon the impugned decision."
    doc = _doc_from_text(text, source_id="plaintiff-s157")

    obs = extract_obligations_from_document(doc)
    ids_before = {o.identity_hash for o in compute_identities(obs)}

    obs_again = extract_obligations_from_document(doc)
    ids_after = {o.identity_hash for o in compute_identities(obs_again)}

    assert ids_before == ids_after


def test_plaintiff_s157_no_reasoning_language():
    """
    Red-flag: payloads must not contain reasoning/compliance terms.
    """
    text = "The Commonwealth must not act upon the impugned decision."
    doc = _doc_from_text(text, source_id="plaintiff-s157")

    obs = extract_obligations_from_document(doc)
    serialized = str(obs).lower()

    forbidden = {
        "therefore",
        "because",
        "implies",
        "invalid",
        "lawful",
        "unlawful",
        "compliant",
        "breach",
    }
    assert forbidden.isdisjoint(serialized.split())
