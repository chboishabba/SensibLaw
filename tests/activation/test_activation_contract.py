from src.activation import FACT_ENVELOPE_VERSION, Fact, FactEnvelope, activation_to_payload, simulate_activation
from src.obligation_identity import compute_identities
from src.obligations import extract_obligations_from_text


TEXT = (
    "The operator must keep records.\n"
    "The licence holder must notify upon commencement and ceases upon revocation."
)


def _envelope(facts: list[Fact]) -> FactEnvelope:
    return FactEnvelope(version=FACT_ENVELOPE_VERSION, issued_at=None, facts=facts)


def test_no_trigger_no_activation():
    obs = extract_obligations_from_text("The operator must keep records.")
    env = _envelope([Fact(key="start", value=True)])
    result = activation_to_payload(simulate_activation(obs, env))
    assert result["active"] == []
    assert result["terminated"] == []


def test_missing_fact_remains_inactive():
    obs = extract_obligations_from_text(TEXT, source_id="doc")
    result = activation_to_payload(simulate_activation(obs, _envelope([])))
    assert set(result["active"]) == set()
    assert set(result["terminated"]) == set()


def test_no_compliance_language():
    obs = extract_obligations_from_text(TEXT, source_id="doc")
    env = _envelope([Fact(key="upon commencement", value=True)])
    result = activation_to_payload(simulate_activation(obs, env))
    serialized = str(result).lower()
    forbidden = {"compliant", "violation", "breach", "satisfied"}
    assert forbidden.isdisjoint(serialized.split())


def test_identity_hashes_preserved():
    obs = extract_obligations_from_text(TEXT, source_id="doc")
    ids = {oid.identity_hash for oid in compute_identities(obs)}
    env = _envelope([Fact(key="upon commencement", value=True)])
    result = activation_to_payload(simulate_activation(obs, env))
    payload_ids = set(result["active"]) | set(result["inactive"]) | set(result["terminated"])
    assert ids == payload_ids


def test_time_words_do_not_infer_activation():
    obs = extract_obligations_from_text(TEXT, source_id="doc")
    env = _envelope([Fact(key="now", value=True), Fact(key="current", value=True)])
    result = activation_to_payload(simulate_activation(obs, env))
    assert result["active"] == []
    assert result["terminated"] == []
import pytest

pytestmark = pytest.mark.redflag
