from __future__ import annotations

from src.wiki_timeline.article_state import (
    STATE_SCHEMA_VERSION,
    build_wiki_article_state,
    build_observations_from_event_candidates,
    build_timeline_projection,
)


def test_build_wiki_article_state_preserves_dated_and_undated_events() -> None:
    state = build_wiki_article_state(
        {
            "wiki": "enwiki",
            "title": "Example",
            "pageid": 1,
            "revid": 100,
            "source_url": "https://en.wikipedia.org/wiki/Example",
            "wikitext": (
                "== Early life ==\n"
                "Jane patted the cat in Brisbane after lunch.\n"
                "On May 5, 2021, Jane called Bob."
            ),
        },
        no_spacy=True,
    )

    assert state["schema_version"] == STATE_SCHEMA_VERSION
    assert len(state["sentence_units"]) >= 2
    assert len(state["timeline_projection"]) == len(state["event_candidates"])
    anchor_statuses = {row["anchor_status"] for row in state["timeline_projection"]}
    assert "none" in anchor_statuses
    assert "explicit" in anchor_statuses
    assert all(row["ordering_basis"] == "source_text_order" for row in state["timeline_projection"])


def test_build_wiki_article_state_derives_regime_vector() -> None:
    state = build_wiki_article_state(
        {
            "wiki": "enwiki",
            "title": "Formal example",
            "pageid": 2,
            "revid": 101,
            "source_url": "https://en.wikipedia.org/wiki/Formal_example",
            "wikitext": (
                "Theorem. Let X be a compact space.\n"
                "There exists a continuous function f.\n"
                "Suppose Y is compact and let g be continuous."
            ),
        },
        no_spacy=True,
    )

    regime = state["regime"]
    assert set(regime) == {"narrative", "descriptive", "formal"}
    assert round(sum(regime.values()), 6) == 1.0
    assert regime["formal"] > regime["narrative"]
    assert regime["formal"] > regime["descriptive"]


def test_observation_builder_emits_actor_action_object_claim_and_anchor_rows() -> None:
    observations = build_observations_from_event_candidates(
        [
            {
                "event_id": "ev1",
                "sentence_unit_id": "unit1",
                "text": "Alice reported Bob resigned on May 5, 2021.",
                "actors": [{"label": "Alice"}],
                "action": "report",
                "objects": [{"title": "Bob resigned"}],
                "claim_bearing": True,
                "attributions": [{"attribution_type": "direct_statement", "step_index": 0}],
                "anchor": {"year": 2021, "month": 5, "day": 5, "kind": "explicit", "precision": "day"},
                "anchor_status": "explicit",
            }
        ]
    )

    predicates = {row["predicate"] for row in observations}
    assert {"actor", "performed_action", "acted_on", "claimed", "communicated", "event_date"} <= predicates


def test_timeline_projection_keeps_order_and_anchor_status() -> None:
    timeline = build_timeline_projection(
        [
            {
                "event_id": "ev2",
                "sentence_unit_id": "unit2",
                "order_index": 2,
                "ordering_basis": "source_text_order",
                "anchor_status": "explicit",
                "text": "On May 5, 2021, Jane called Bob.",
                "actors": [{"label": "Jane"}],
                "objects": [{"title": "Bob"}],
            },
            {
                "event_id": "ev1",
                "sentence_unit_id": "unit1",
                "order_index": 1,
                "ordering_basis": "source_text_order",
                "anchor_status": "none",
                "text": "Jane patted the cat.",
                "actors": [{"label": "Jane"}],
                "objects": [{"title": "cat"}],
            },
        ]
    )

    assert [row["event_id"] for row in timeline] == ["ev1", "ev2"]
    assert [row["anchor_status"] for row in timeline] == ["none", "explicit"]
