from __future__ import annotations

from scripts import wiki_timeline_aoo_extract as ext


def test_canonical_action_fallback_uses_lemma_map_for_reported() -> None:
    action, meta = ext._canonical_action_from_doc(None, "reported")
    assert action == "report"
    assert isinstance(meta, dict)
    assert meta.get("source") == "fallback:action_lemmas"
    assert meta.get("surface") == "reported"


def test_canonical_action_fallback_handles_not_prefix_without_new_variant() -> None:
    action, meta = ext._canonical_action_from_doc(None, "not_voted")
    assert action == "vote"
    assert isinstance(meta, dict)
    assert meta.get("source") == "fallback:action_lemmas"


def test_text_fallback_does_not_promote_nominal_ing_phrase() -> None:
    action = ext._fallback_action(
        "The September 11 terrorist attacks were a major turning point in Bush's presidency."
    )
    assert action is None
