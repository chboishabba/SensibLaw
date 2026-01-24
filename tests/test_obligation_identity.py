from datetime import date

from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom, RuleReference
from src.obligations import extract_obligations_from_document, extract_obligations_from_text
from src.obligation_identity import (
    ObligationIdentity,
    compute_obligation_identity,
    diff_obligations,
)


def _doc(body: str, refs: list[RuleReference], source_id: str = "doc") -> Document:
    metadata = DocumentMetadata(jurisdiction="NSW", citation="CIT", date=date(2023, 1, 1), provenance=source_id)
    prov = Provision(text=body, rule_atoms=[RuleAtom(references=refs)])
    return Document(metadata=metadata, body=body, provisions=[prov])


def _identities_for_body(body: str, refs: list[RuleReference]) -> list[ObligationIdentity]:
    obligations = extract_obligations_from_text(body, references=refs, source_id="doc")
    return [
        compute_obligation_identity(ob, idx)
        for idx, ob in enumerate(obligations)
    ]


def test_obligation_identity_stable_under_spacing():
    base = "A person must not enter if the gate is locked."
    noisy = "A  person  must  not enter if   the gate is locked."
    ref = RuleReference(work="Crimes Act 1914", provenance={"clause_id": "doc-clause-0"})
    base_ids = _identities_for_body(base, [ref])
    noisy_ids = _identities_for_body(noisy, [ref])
    assert [o.identity_hash for o in base_ids] == [o.identity_hash for o in noisy_ids]


def test_obligation_diff_detects_added():
    old = "The operator must keep records."
    new = "The operator must keep records. The operator must file returns."
    ref = RuleReference(work="Safety Act 2000", provenance={"clause_id": "doc-clause-0"})
    ref2 = RuleReference(work="Safety Act 2000", provenance={"clause_id": "doc-clause-1"})
    old_ids = _identities_for_body(old, [ref])
    new_ids = _identities_for_body(new, [ref, ref2])
    diff = diff_obligations(old_ids, new_ids)
    assert len(diff.added) == 1
    assert not diff.removed
    assert diff.unchanged


def test_clause_renumbering_no_diff():
    text_a = "1. An officer must inspect. 2. An officer may warn."
    text_b = "A. An officer must inspect. B. An officer may warn."
    ref1a = RuleReference(work="Act 2000", provenance={"clause_id": "doc-clause-0"})
    ref2a = RuleReference(work="Act 2000", provenance={"clause_id": "doc-clause-1"})
    ref1b = RuleReference(work="Act 2000", provenance={"clause_id": "doc-clause-0"})
    ref2b = RuleReference(work="Act 2000", provenance={"clause_id": "doc-clause-1"})
    ids_a = _identities_for_body(text_a, [ref1a, ref2a])
    ids_b = _identities_for_body(text_b, [ref1b, ref2b])
    diff = diff_obligations(ids_a, ids_b)
    assert not diff.added
    assert not diff.removed


def test_actor_changes_identity():
    base = "The operator must keep records."
    alt = "The pilot must keep records."
    base_ids = _identities_for_body(base, [])
    alt_ids = _identities_for_body(alt, [])
    assert base_ids[0].identity_hash != alt_ids[0].identity_hash


def test_actor_identity_stable_under_spacing():
    base = "The operator must keep records."
    noisy = "The  operator  must   keep records."
    base_ids = _identities_for_body(base, [])
    noisy_ids = _identities_for_body(noisy, [])
    assert base_ids[0].identity_hash == noisy_ids[0].identity_hash


def test_actor_flag_can_disable_binding():
    text = "The operator must keep records."
    ids_with_actor = _identities_for_body(text, [])
    obligations_no_actor = extract_obligations_from_text(
        text, references=[], source_id="doc", enable_actor_binding=False
    )
    ids_without_actor = [
        compute_obligation_identity(ob, idx) for idx, ob in enumerate(obligations_no_actor)
    ]
    assert ids_with_actor[0].identity_hash != ids_without_actor[0].identity_hash
    assert ids_without_actor[0].actor is None
