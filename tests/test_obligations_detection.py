from datetime import date
from pathlib import Path

from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom, RuleReference
from src.obligations import extract_obligations_from_document, extract_obligations_from_text


def _doc(body: str, refs: list[RuleReference], source_id: str = "doc") -> Document:
    metadata = DocumentMetadata(jurisdiction="NSW", citation="CIT", date=date(2023, 1, 1), provenance=source_id)
    prov = Provision(text=body, rule_atoms=[RuleAtom(references=refs)])
    return Document(metadata=metadata, body=body, provisions=[prov])


def test_obligation_detects_must_with_reference():
    body = "A person must comply with the Crimes Act 1914."
    ref = RuleReference(work="Crimes Act 1914", provenance={"clause_id": "doc-clause-0"})
    obligations = extract_obligations_from_text(body, references=[ref], source_id="doc")
    assert len(obligations) == 1
    ob = obligations[0]
    assert ob.type == "obligation"
    assert ob.modality == "must"
    assert len(ob.reference_identities) == 1


def test_permission_detects_may_without_inventing_refs():
    body = "An officer may issue a permit."
    obligations = extract_obligations_from_text(body, references=[], source_id="doc")
    assert len(obligations) == 1
    ob = obligations[0]
    assert ob.type == "permission"
    assert ob.reference_identities == set()


def test_prohibition_detects_must_not_stable_under_spacing():
    base_body = "The driver must not drive while intoxicated."
    noisy_body = "The driver must   not drive while intoxicated."
    ref = RuleReference(work="Road Transport Act 2013", provenance={"clause_id": "doc-clause-0"})
    base = extract_obligations_from_text(base_body, references=[ref], source_id="doc")
    noisy = extract_obligations_from_text(noisy_body, references=[ref], source_id="doc")
    assert [(o.type, o.modality, o.reference_identities) for o in base] == [
        (o.type, o.modality, o.reference_identities) for o in noisy
    ]


def test_exclusion_does_not_apply():
    body = "This Part does not apply to ships registered overseas."
    ref = RuleReference(work="Marine Safety Act 1998", provenance={"clause_id": "doc-clause-0"})
    obligations = extract_obligations_from_text(body, references=[ref], source_id="doc")
    assert len(obligations) == 1
    ob = obligations[0]
    assert ob.type == "exclusion"
    assert "does not apply" in ob.modality
    assert len(ob.reference_identities) == 1


def test_clause_boundary_non_interference():
    body = "The operator must follow the Safety Act 2000. The pilot must follow the Aviation Act 1995."
    ref1 = RuleReference(work="Safety Act 2000", provenance={"clause_id": "doc-clause-0"})
    ref2 = RuleReference(work="Aviation Act 1995", provenance={"clause_id": "doc-clause-1"})
    doc = _doc(body, [ref1, ref2], source_id="doc")
    obligations = extract_obligations_from_document(doc)
    assert len(obligations) == 2
    first_refs = obligations[0].reference_identities
    second_refs = obligations[1].reference_identities
    assert first_refs != second_refs
    assert len(first_refs) == 1
    assert len(second_refs) == 1


def test_actor_extracted_clause_local():
    body = "The operator must keep records."
    obligations = extract_obligations_from_text(body, references=[], source_id="doc")
    assert len(obligations) == 1
    actor = obligations[0].actor
    assert actor is not None
    assert actor.normalized == "the operator"
    assert actor.clause_id == obligations[0].clause_id


def test_missing_actor_does_not_suppress_obligation():
    body = "Must comply with the Act."
    obligations = extract_obligations_from_text(body, references=[], source_id="doc")
    assert len(obligations) == 1
    assert obligations[0].actor is None


def test_actor_fixture_variants(tmp_path):
    fixtures = Path(__file__).parent / "fixtures" / "actors"

    distinct = (fixtures / "distinct_actors.txt").read_text().strip()
    obligations = extract_obligations_from_text(distinct, references=[], source_id="doc")
    assert len(obligations) == 2
    assert {ob.actor.normalized for ob in obligations if ob.actor} == {"the operator", "the pilot"}

    missing = (fixtures / "missing_actor.txt").read_text().strip()
    missing_obs = extract_obligations_from_text(missing, references=[], source_id="doc")
    assert len(missing_obs) == 1
    assert missing_obs[0].actor is None

    noisy = (fixtures / "ocr_noise_actor.txt").read_text().strip()
    noisy_obs = extract_obligations_from_text(noisy, references=[], source_id="doc")
    assert len(noisy_obs) == 1
    assert noisy_obs[0].actor is not None
    assert noisy_obs[0].actor.normalized == "the ope rator"

    multi = (fixtures / "multi_actor_conjunction.txt").read_text().strip()
    multi_obs = extract_obligations_from_text(multi, references=[], source_id="doc")
    assert len(multi_obs) == 1
    assert multi_obs[0].actor is not None
    assert multi_obs[0].actor.normalized == "the operator and the pilot"

    titled = (fixtures / "titled_actor.txt").read_text().strip()
    titled_obs = extract_obligations_from_text(titled, references=[], source_id="doc")
    assert len(titled_obs) == 1
    assert titled_obs[0].actor is not None
    assert titled_obs[0].actor.normalized == "the minister for health"
