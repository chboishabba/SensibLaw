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
        citation="Mabo v Queensland (No 2) (1992) 175 CLR 1",
        date=date(1992, 6, 3),
        provenance="HCA_1992_Mabo_No2",
    )
    prov = Provision(text=body, rule_atoms=[RuleAtom()])
    return Document(metadata=meta, body=body, provisions=[prov])


def test_mabo_no2_yields_declarative_obligation():
    body = "The Crown must recognize that the common law of Australia recognises a form of native title."
    doc = _doc(body)
    obligations = list(extract_obligations_from_document(doc))
    assert obligations, "Expected at least one declarative obligation."
    assert any(ob.modality == "must" for ob in obligations)


def test_mabo_no2_identities_are_stable():
    body = "Native title continues unless extinguished by valid sovereign act."
    doc = _doc(body)
    obs1 = list(extract_obligations_from_document(doc))
    ids1 = {oid.identity_hash for oid in compute_identities(obs1)}

    obs2 = list(extract_obligations_from_document(doc))
    ids2 = {oid.identity_hash for oid in compute_identities(obs2)}

    assert ids1 == ids2
