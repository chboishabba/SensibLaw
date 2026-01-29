from datetime import date

import pytest

from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom
from src.obligations import extract_obligations_from_document
from src.obligation_identity import compute_identities

pytestmark = pytest.mark.redflag


def _doc(body: str) -> Document:
    meta = DocumentMetadata(
        jurisdiction="HCA",
        citation="House v The King (1936) 55 CLR 499",
        date=date(1936, 8, 14),
        provenance="HCA_1936_House_v_The_King",
    )
    prov = Provision(text=body, rule_atoms=[RuleAtom()])
    return Document(metadata=meta, body=body, provisions=[prov])


def test_house_v_the_king_yields_obligation():
    body = (
        "The appellate court must not interfere with the exercise of a discretion unless it is shown"
        " that the judge acted upon a wrong principle."
    )
    doc = _doc(body)
    obligations = list(extract_obligations_from_document(doc))
    assert obligations, "Expected at least one obligation from the canonical formulation."
    assert any("must" in ob.modality for ob in obligations)


def test_house_v_the_king_identities_are_stable():
    body = (
        "The appellate court must not interfere with the exercise of a discretion unless error is shown."
    )
    doc = _doc(body)
    obs1 = list(extract_obligations_from_document(doc))
    ids1 = {oid.identity_hash for oid in compute_identities(obs1)}

    obs2 = list(extract_obligations_from_document(doc))
    ids2 = {oid.identity_hash for oid in compute_identities(obs2)}

    assert ids1 == ids2
