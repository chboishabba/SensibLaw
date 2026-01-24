from datetime import date

from src.models.document import Document, DocumentMetadata, Provision
from src.models.provision import RuleAtom, RuleReference
from src.obligations import extract_obligations_from_text
from src.obligation_identity import compute_obligation_identity


def _doc(body: str, refs: list[RuleReference], source_id: str = "doc") -> Document:
    metadata = DocumentMetadata(jurisdiction="NSW", citation="CIT", date=date(2023, 1, 1), provenance=source_id)
    prov = Provision(text=body, rule_atoms=[RuleAtom(references=refs)])
    return Document(metadata=metadata, body=body, provisions=[prov])


def test_action_object_distinct_actions():
    body_keep = "The operator must keep records."
    body_maintain = "The operator must maintain records."
    obs_keep = extract_obligations_from_text(body_keep, references=[], source_id="doc")
    obs_maintain = extract_obligations_from_text(body_maintain, references=[], source_id="doc")
    assert obs_keep[0].action.normalized == "keep"
    assert obs_maintain[0].action.normalized == "maintain"
    id_keep = compute_obligation_identity(obs_keep[0], 0).identity_hash
    id_maintain = compute_obligation_identity(obs_maintain[0], 0).identity_hash
    assert id_keep != id_maintain


def test_action_object_spacing_noise_stable():
    base = "The operator must keep records."
    noisy = "The  operator  must   keep   records."
    base_obs = extract_obligations_from_text(base, references=[], source_id="doc")
    noisy_obs = extract_obligations_from_text(noisy, references=[], source_id="doc")
    assert base_obs[0].action.normalized == "keep"
    assert noisy_obs[0].action.normalized == "keep"
    base_id = compute_obligation_identity(base_obs[0], 0).identity_hash
    noisy_id = compute_obligation_identity(noisy_obs[0], 0).identity_hash
    assert base_id == noisy_id


def test_action_object_missing_object_allowed():
    body = "An officer must comply."
    obs = extract_obligations_from_text(body, references=[], source_id="doc")
    assert obs[0].action.normalized == "comply"
    assert obs[0].obj is None


def test_action_object_clause_numbering_stable():
    text_a = "1. The operator must keep records."
    text_b = "(a) The operator must keep records."
    obs_a = extract_obligations_from_text(text_a, references=[], source_id="doc")
    obs_b = extract_obligations_from_text(text_b, references=[], source_id="doc")
    id_a = compute_obligation_identity(obs_a[0], 0).identity_hash
    id_b = compute_obligation_identity(obs_b[0], 0).identity_hash
    assert id_a == id_b
