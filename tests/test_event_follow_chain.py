from SensibLaw.src.follow.event_follow_chain import (
    EventFollowInput,
    build_event_follow_unit,
)


def test_event_follow_chain_preserves_separation():
    follow_input = EventFollowInput(
        event_id="2026-UNSC-123",
        event_summary="Domestic legislature observes UN Charter breach and cites ICJ guidance.",
        un_charter_article="Article 2(4)",
        icj_case_id="ICJ-2021-Dispute",
        domestic_permission_source="national_parliament_daily",
        domestic_permission_scope="national_following_resolution_42",
    )

    follow_unit = build_event_follow_unit(follow_input)
    chain = follow_unit["chain"]
    separation = follow_unit["separation"]

    assert chain["un_charter"]["authority_type"] == "treaty"
    assert chain["icj"]["authority_type"] == "international_judgment"
    assert chain["domestic_permission"]["international_validity"] is False
    assert separation["international_validity"] is True
    assert separation["domestic_permission_isolated"] is True
