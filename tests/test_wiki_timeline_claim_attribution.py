from __future__ import annotations

import pytest

from scripts import wiki_timeline_aoo_extract as ext


def test_annotate_claim_bearing_steps_marks_epistemic_actions() -> None:
    steps = [
        {"action": "estimate", "subjects": ["George W. Bush"]},
        {"action": "meet", "subjects": ["George W. Bush"]},
        {"action": "report", "subjects": ["Gallup"]},
    ]
    idx = ext._annotate_claim_bearing_steps(None, steps, "ev:test", ["estimate", "report", "say"])
    assert idx == [0, 2]
    assert steps[0]["claim_bearing"] is True
    assert steps[1]["claim_bearing"] is False
    assert steps[2]["claim_bearing"] is True
    assert steps[0]["claim_modality"] == "projection"
    assert steps[2]["claim_modality"] == "reported"
    assert steps[2]["claim_id"] == "ev:test:step:2"


def test_build_event_attributions_types_direct_vs_reported() -> None:
    steps = [
        {"action": "estimate", "subjects": ["George W. Bush"], "claim_bearing": True, "claim_id": "ev:1:step:0"},
        {"action": "report", "subjects": ["Gallup"], "claim_bearing": True, "claim_id": "ev:1:step:1"},
        {"action": "meet", "subjects": ["George W. Bush"], "claim_bearing": False},
    ]
    attrs = ext._build_event_attributions(
        event_id="ev:1",
        steps=steps,
        source_entity_id="source:test",
        communication_verbs=["report", "say"],
    )
    assert len(attrs) == 2
    by_step = {int(a["step_index"]): a for a in attrs}
    assert by_step[0]["attribution_type"] == "direct_statement"
    assert by_step[0]["attributed_actor_id"] == "George W. Bush"
    assert by_step[1]["attribution_type"] == "reported_statement"
    assert by_step[1]["attributed_actor_id"] == "Gallup"


def test_build_source_entity_from_snapshot_uses_wikipedia_type() -> None:
    source = ext._build_source_entity(
        {
            "title": "George W. Bush",
            "source_url": "https://en.wikipedia.org/wiki/George_W._Bush",
            "revid": 1336322390,
            "rev_timestamp": "2026-02-03T03:42:23Z",
        }
    )
    assert source["type"] == "wikipedia_article"
    assert source["title"] == "George W. Bush"
    assert source["url"] == "https://en.wikipedia.org/wiki/George_W._Bush"
    assert source["version_hash"] == "1336322390"
    assert str(source["id"]).startswith("source:")


def test_normalize_requester_surface_strips_possessive_noise() -> None:
    assert ext._normalize_requester_surface("President Obama 's") == "President Obama"
    assert ext._normalize_requester_surface("Obama's") == "Obama"


def test_normalize_subject_label_strips_leading_the() -> None:
    assert ext._normalize_subject_label("the United States") == "United States"
    assert ext._normalize_subject_label("The United States") == "United States"


def test_resolve_requester_label_uses_alias_map_through_title_and_surname() -> None:
    alias_map = {"Obama": "Barack Obama"}
    assert ext._resolve_requester_label("President Obama 's", alias_map) == "Barack Obama"


def test_infer_requester_from_request_steps() -> None:
    steps = [
        {"action": "establish", "subjects": ["George W. Bush"]},
        {"action": "request", "subjects": ["U.S. President", "Barack Obama"]},
    ]
    assert ext._infer_requester_from_steps(steps, "U.S. President") == "Barack Obama"


def test_extract_requester_from_doc_resolves_possessive_title() -> None:
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    doc = nlp("In January 2010, at President Obama's request, Bush and Bill Clinton established the fund.")
    requester, resolved, has_title = ext._extract_requester_from_doc(doc, {"Obama": "Barack Obama"})
    assert requester in {"President Obama", "Obama"}
    assert resolved == "Barack Obama"
    assert has_title is True


def test_subjects_for_action_strips_leading_the_from_dependency_subject() -> None:
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    doc = nlp("In 2007, the United States entered the longest post-World War II recession.")
    subjects = ext._subjects_for_action(doc, "enter", [], "George W. Bush", "Bush")
    assert "United States" in subjects
    assert all(s != "the United States" for s in subjects)


def test_canonical_action_from_doc_emits_canonical_morphology_enums() -> None:
    nlp, _, _ = ext._try_load_spacy("en_core_web_sm")
    if nlp is None:
        pytest.skip("spaCy model unavailable")
    doc = nlp("Gallup reported that voters approved of Bush.")
    lemma, meta = ext._canonical_action_from_doc(doc, "reported")
    assert lemma == "report"
    assert isinstance(meta, dict)
    assert meta.get("tense") in {"past", "present", "future", "unknown"}
    assert meta.get("aspect") in {"simple", "progressive", "perfect", "perfect_progressive", "unknown"}
    assert meta.get("verb_form") in {"finite", "infinitive", "participle", "gerund", "unknown"}
    assert meta.get("voice") in {"active", "passive", "middle", "unknown"}
    assert meta.get("mood") in {"indicative", "conditional", "imperative", "subjunctive", "unknown"}
    assert meta.get("modality") in {"asserted", "reported", "projected", "estimated", "alleged", "inferred"}


def test_requester_coverage_summary_counts_missing_requesters() -> None:
    events = [
        {
            "event_id": "ev:1",
            "steps": [{"action": "request"}],
            "text": "At President Obama's request, Bush established the fund.",
            "actors": [{"role": "requester", "resolved": "Barack Obama"}],
        },
        {
            "event_id": "ev:2",
            "steps": [{"action": "request"}],
            "text": "At the President's request, Clinton joined the effort.",
            "actors": [{"role": "subject", "resolved": "George W. Bush"}],
        },
        {
            "event_id": "ev:3",
            "steps": [{"action": "meet"}],
            "text": "They met in New York City.",
            "actors": [{"role": "subject", "resolved": "George W. Bush"}],
        },
    ]
    summary = ext._requester_coverage_summary(events)
    assert summary["total_events"] == 3
    assert summary["request_signal_events"] == 2
    assert summary["requester_events"] == 1
    assert summary["missing_requester_event_ids"] == ["ev:2"]
