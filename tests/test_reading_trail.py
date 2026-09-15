from __future__ import annotations

import pytest

from src.sensiblaw.interfaces.reading_trail import (
    FollowTarget,
    IntentAdmissionError,
    build_mabo_reading_fixture,
    parse_reading_intent,
    project_reading_view,
    reduce_reading_intent,
)


def test_mabo_fixture_preserves_constituent_and_composite_overlapping_spans():
    state, projection = build_mabo_reading_fixture()
    native_title = state.world.targets["concept:native_title"]
    title = state.world.targets["lexeme:title"]

    assert native_title.char_start < title.char_start
    assert title.char_end == native_title.char_end
    assert native_title.target_id in projection.visible_target_ids
    assert title.target_id in projection.visible_target_ids
    assert native_title.semantic_ref != title.semantic_ref


def test_follow_target_changes_navigation_not_world_or_identity():
    state, _ = build_mabo_reading_fixture()
    world_before = state.world

    next_state = reduce_reading_intent(
        state,
        FollowTarget(target_id="concept:native_title"),
    )

    assert next_state.world is world_before
    assert next_state.active_target_id == "concept:native_title"
    assert next_state.trail == ("concept:native_title",)
    assert (
        next_state.world.targets["concept:native_title"].semantic_ref
        == "concept:native_title"
    )
    assert next_state.world.targets["lexeme:title"].semantic_ref == "lexeme:title"


def test_hidden_target_remains_in_world_bucket():
    state, projection = build_mabo_reading_fixture()

    assert "context:wikipedia_mabo" in state.world.targets
    assert "context:wikipedia_mabo" not in projection.visible_target_ids


def test_context_target_does_not_acquire_legal_authority():
    state, _ = build_mabo_reading_fixture()
    context = state.world.targets["context:wikipedia_mabo"]
    mabo = state.world.targets["legal_ref:mabo_v_queensland_no_2"]

    assert context.authority_kind == "context"
    assert mabo.authority_kind == "legal_authority_reference"


def test_malformed_or_unknown_intent_is_rejected_before_reduction():
    state, _ = build_mabo_reading_fixture()

    with pytest.raises(IntentAdmissionError):
        parse_reading_intent({"kind": "FollowTarget"})

    with pytest.raises(IntentAdmissionError):
        parse_reading_intent({"kind": "RewriteCanonicalEntity", "targetId": "x"})

    unknown = parse_reading_intent(
        {"kind": "FollowTarget", "targetId": "missing"}
    )
    with pytest.raises(IntentAdmissionError):
        reduce_reading_intent(state, unknown)

    assert state.trail == ()
    assert state.active_target_id is None


def test_following_composite_does_not_follow_constituent():
    state, _ = build_mabo_reading_fixture()
    next_state = reduce_reading_intent(
        state,
        parse_reading_intent(
            {"kind": "FollowTarget", "targetId": "concept:native_title"}
        ),
    )

    assert next_state.trail == ("concept:native_title",)
    assert "lexeme:title" not in next_state.trail


def test_wire_projection_preserves_overlapping_targets_and_span_contract():
    state, projection = build_mabo_reading_fixture()
    view = project_reading_view(state, projection)
    by_id = {target["targetId"]: target for target in view["targets"]}

    assert (
        by_id["concept:native_title"]["charEnd"]
        == by_id["lexeme:title"]["charEnd"]
    )
    assert (
        by_id["concept:native_title"]["charStart"]
        < by_id["lexeme:title"]["charStart"]
    )
    assert all(target["sourceArtifactId"] for target in view["targets"])
    assert by_id["legal_ref:mabo_v_queensland_no_2"]["roleOverlays"] == ["subject"]
    assert view["activeTargetId"] is None


def test_projection_hides_context_without_deleting_it_from_world():
    state, projection = build_mabo_reading_fixture()
    view = project_reading_view(state, projection)

    assert all(
        target["targetId"] != "context:wikipedia_mabo"
        for target in view["targets"]
    )
    assert "context:wikipedia_mabo" in state.world.targets


def test_mabo_target_uses_existing_canonical_au_semantic_key():
    state, _ = build_mabo_reading_fixture()
    target = state.world.targets["legal_ref:mabo_v_queensland_no_2"]

    assert target.semantic_ref == "legal_ref:mabo_v_queensland_no_2"


def test_role_overlay_does_not_replace_semantic_reference():
    state, _ = build_mabo_reading_fixture()
    mabo = state.world.targets["legal_ref:mabo_v_queensland_no_2"]
    action = state.world.targets["action:recognised"]

    assert mabo.role_overlays == ("subject",)
    assert mabo.semantic_ref == "legal_ref:mabo_v_queensland_no_2"
    assert action.role_overlays == ("predicate",)
    assert action.semantic_ref == "action:recognised"
