import yaml

from src.obligation_alignment import ALIGNMENT_SCHEMA_VERSION, align_obligations, alignment_to_payload
from src.obligation_identity import compute_identities
from src.obligations import extract_obligations_from_text
from src.obligation_views import EXPLANATION_SCHEMA_VERSION, QUERY_SCHEMA_VERSION


def _normalize_tokens(text: str):
    return [t.strip().lower() for t in text.split() if t.strip()]


def test_no_obligation_without_modal():
    text = "The operator keep records."  # no modal
    obs = extract_obligations_from_text(text)
    assert obs == []  # no invented obligations


def test_no_edges_without_triggers():
    text = "The operator must keep records."  # no condition/exception words
    obs = extract_obligations_from_text(text)
    assert obs[0].conditions == []


def test_identity_not_affected_by_scope_or_lifecycle():
    base = extract_obligations_from_text("The operator must keep records.")
    scoped = extract_obligations_from_text("The operator must keep records within 7 days while licensed.")
    id_base = compute_identities(base)[0].identity_hash
    id_scoped = compute_identities(scoped)[0].identity_hash
    assert id_base == id_scoped


def test_alignment_requires_real_delta():
    text = "The operator must keep records."
    left = extract_obligations_from_text(text)
    right = extract_obligations_from_text("(1)  The operator   must keep records.")
    report = align_obligations(left, right)
    assert not report.modified
    payload = alignment_to_payload(report)
    assert payload["version"] == ALIGNMENT_SCHEMA_VERSION


def test_normalized_tokens_are_text_derived():
    text = "The Minister must approve."
    obs = extract_obligations_from_text(text)
    actor_norm = obs[0].actor.normalized
    clause_tokens = _normalize_tokens(text)
    for tok in actor_norm.split():
        assert tok in clause_tokens  # no ontology expansion


def test_schema_versions_frozen():
    assert QUERY_SCHEMA_VERSION == "obligation.query.v1"
    assert EXPLANATION_SCHEMA_VERSION == "obligation.explanation.v1"
    assert ALIGNMENT_SCHEMA_VERSION == "obligation.alignment.v1"

    with open("schemas/obligation.alignment.v1.schema.yaml", "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    assert schema["properties"]["version"]["const"] == ALIGNMENT_SCHEMA_VERSION
