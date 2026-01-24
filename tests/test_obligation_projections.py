from src.obligations import extract_obligations_from_text
from src.obligation_projections import actor_view, action_view, clause_view, timeline_view


def _sample_obligations():
    text = (
        "The operator must keep records within 7 days.\n"
        "A person must not enter the area on the premises.\n"
        "The licence holder must notify on commencement and ceases upon revocation."
    )
    return extract_obligations_from_text(text)


def test_actor_view_groups_and_sorts():
    obligations = _sample_obligations()
    view = actor_view(obligations)
    actors = [v["actor"] for v in view]
    assert actors == ["person", "the licence holder", "the operator"]
    assert all(len(v["obligations"]) == 1 for v in view)


def test_action_view_groups_and_sorts():
    obligations = _sample_obligations()
    view = action_view(obligations)
    actions = [v["action"] for v in view]
    assert actions == ["enter", "keep", "notify"]
    notify_entry = next(v for v in view if v["action"] == "notify")
    assert notify_entry["obligations"][0]["modality"] == "must"


def test_clause_view_is_deterministic():
    obligations = clause_view(_sample_obligations())
    clause_ids = [ob["clause_id"] for ob in obligations]
    assert clause_ids == sorted(clause_ids)


def test_timeline_view_keeps_lifecycle_descriptive():
    obligations = _sample_obligations()
    timeline = timeline_view(obligations)
    # last clause has lifecycle data
    last = timeline[-1]
    kinds = [lc["kind"] for lc in last["lifecycle"]]
    assert "activation" in kinds and "termination" in kinds
    assert last["action"] == "notify"
