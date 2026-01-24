from src.obligations import extract_obligations_from_text
from src.obligation_identity import compute_obligation_identity


def test_time_scope_within_days():
    body = "The operator must notify within 7 days."
    obs = extract_obligations_from_text(body, references=[], source_id="doc")
    scopes = [s for s in obs[0].scopes if s.category == "time"]
    assert scopes
    assert scopes[0].normalized.startswith("within 7 days")


def test_place_scope_on_premises():
    body = "The operator must keep records on the premises."
    obs = extract_obligations_from_text(body, references=[], source_id="doc")
    scopes = [s for s in obs[0].scopes if s.category == "place"]
    assert scopes
    assert scopes[0].normalized == "on the premises"


def test_context_scope_during_operations():
    body = "The operator must keep records during operations."
    obs = extract_obligations_from_text(body, references=[], source_id="doc")
    scopes = [s for s in obs[0].scopes if s.category == "context"]
    assert scopes
    assert scopes[0].normalized.startswith("during")


def test_scope_does_not_change_identity():
    with_scope = "The operator must keep records on the premises."
    without_scope = "The operator must keep records."
    a = extract_obligations_from_text(with_scope, references=[], source_id="doc")
    b = extract_obligations_from_text(without_scope, references=[], source_id="doc")
    a_id = compute_obligation_identity(a[0], 0).identity_hash
    b_id = compute_obligation_identity(b[0], 0).identity_hash
    assert a_id == b_id
