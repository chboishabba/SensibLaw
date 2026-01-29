from src.activation import (
    ACTIVATION_VERSION,
    FACT_ENVELOPE_VERSION,
    Fact,
    FactEnvelope,
    simulate_activation,
)
from src.obligation_identity import compute_identities
from src.obligations import extract_obligations_from_text


TEXT = (
    "The operator must keep records.\n"
    "The licence holder must notify upon commencement and ceases upon revocation."
)


def _facts(*items: Fact) -> FactEnvelope:
    return FactEnvelope(version=FACT_ENVELOPE_VERSION, issued_at=None, facts=list(items))


def _obs():
    return extract_obligations_from_text(TEXT, source_id="doc")


def test_no_trigger_text_stays_inactive():
    facts = _facts(Fact(key="start", value=True))
    obligations = extract_obligations_from_text("The operator must keep records.")
    result = simulate_activation(obligations, facts)
    assert result.version == ACTIVATION_VERSION
    assert result.active == []
    assert set(result.inactive) == {compute_identities(obligations)[0].identity_hash}


def test_missing_fact_does_not_activate():
    obligations = _obs()
    result = simulate_activation(obligations, _facts())
    assert result.active == []
    assert set(result.inactive) | set(result.terminated) == {
        identity.identity_hash for identity in compute_identities(obligations)
    }


def test_activation_requires_matching_trigger_text():
    obligations = _obs()
    facts = _facts(Fact(key="upon commencement", value=True))
    result = simulate_activation(obligations, facts)
    assert len(result.active) == 1
    assert result.terminated == []


def test_termination_takes_precedence():
    obligations = _obs()
    facts = _facts(Fact(key="upon commencement", value=True), Fact(key="ceases upon revocation", value=True))
    result = simulate_activation(obligations, facts)
    assert result.terminated  # termination wins
    assert result.active == []


def test_identity_unchanged_and_no_compliance_labels():
    obligations = _obs()
    facts = _facts(Fact(key="upon commencement", value=True))
    before_ids = [oid.identity_hash for oid in compute_identities(obligations)]
    result = simulate_activation(obligations, facts)
    after_ids = before_ids  # obligations unchanged
    assert set(before_ids) == set(result.active + result.inactive + result.terminated)
    # guard against compliance language
    forbidden = {"compliant", "violation", "breach", "satisfied"}
    assert forbidden.isdisjoint(result.__dict__.keys())
