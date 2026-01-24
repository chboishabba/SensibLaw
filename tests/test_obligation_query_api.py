from src.obligations import extract_obligations_from_text
from src.obligation_views import (
    QUERY_SCHEMA_VERSION,
    obligations_to_query_payload,
    query_obligations,
)


def _sample_obligations(enable_action: bool | None = None):
    text = (
        "The operator must keep records within 7 days.\n"
        "A person must not enter the area on the premises.\n"
        "The licence holder must notify on commencement and ceases upon revocation."
    )
    return extract_obligations_from_text(text, enable_action_binding=enable_action)


def test_query_filters_by_actor_action_scope_and_lifecycle():
    obligations = _sample_obligations()

    actor_matches = query_obligations(obligations, actor="the operator")
    assert [ob.modality for ob in actor_matches] == ["must"]
    assert actor_matches[0].action and actor_matches[0].action.normalized == "keep"

    action_matches = query_obligations(obligations, action="enter")
    assert len(action_matches) == 1
    assert action_matches[0].modality == "must not"

    time_scoped = query_obligations(obligations, scope_category="time")
    assert [ob.clause_id for ob in time_scoped] == [obligations[0].clause_id]

    termination = query_obligations(obligations, lifecycle_kind="termination")
    assert [ob.action.normalized for ob in termination if ob.action] == ["notify"]


def test_query_respects_action_binding_flag():
    obligations = _sample_obligations(enable_action=False)
    assert query_obligations(obligations, action="keep") == []


def test_query_results_are_ordered_and_noise_stable():
    base_obs = extract_obligations_from_text("The operator must keep records.")
    noisy_obs = extract_obligations_from_text("(a)  The operator   must keep records.")

    base_actions = [ob.action.normalized for ob in query_obligations(base_obs, action="keep") if ob.action]
    noisy_actions = [ob.action.normalized for ob in query_obligations(noisy_obs, action="keep") if ob.action]
    assert base_actions == noisy_actions == ["keep"]

    payload = obligations_to_query_payload(base_obs)
    assert payload["version"] == QUERY_SCHEMA_VERSION
    assert payload["results"][0]["modality"] == "must"
