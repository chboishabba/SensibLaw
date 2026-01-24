from src.obligations import extract_obligations_from_text
from src.obligation_identity import compute_obligation_identity


def test_activation_trigger_on_commencement():
    body = "The operator must comply on commencement."
    obs = extract_obligations_from_text(body, references=[], source_id="doc")
    activations = [t for t in obs[0].lifecycle if t.kind == "activation"]
    assert activations
    assert activations[0].normalized.startswith("on")


def test_termination_trigger_until_revoked():
    body = "The licence must remain displayed until revoked."
    obs = extract_obligations_from_text(body, references=[], source_id="doc")
    terms = [t for t in obs[0].lifecycle if t.kind == "termination"]
    assert terms
    assert "until" in terms[0].normalized


def test_lifecycle_metadata_does_not_change_identity():
    with_life = "The operator must comply on commencement."
    without_life = "The operator must comply."
    a = extract_obligations_from_text(with_life, references=[], source_id="doc")
    b = extract_obligations_from_text(without_life, references=[], source_id="doc")
    a_id = compute_obligation_identity(a[0], 0).identity_hash
    b_id = compute_obligation_identity(b[0], 0).identity_hash
    assert a_id == b_id
