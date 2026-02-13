from __future__ import annotations

from scripts import wiki_timeline_aoo_extract as ext


def test_row_identity_keys_include_exact_hint_identity() -> None:
    row = {
        "title": "Bush",
        "source": "dep_object",
        "resolver_hints": [
            {"lane": "sentence_link", "kind": "exact", "title": "George W. Bush", "score": 1.0}
        ],
    }
    keys = ext._row_identity_keys(row)
    assert "george w bush" in keys
    assert "bush" in keys


def test_preferred_entity_label_uses_exact_hint_title() -> None:
    row = {
        "title": "Bush",
        "source": "dep_object",
        "resolver_hints": [
            {"lane": "sentence_link", "kind": "exact", "title": "George W. Bush", "score": 1.0}
        ],
    }
    assert ext._preferred_entity_label("Bush", row) == "George W. Bush"


def test_step_subject_key_is_order_insensitive() -> None:
    left = ext._step_subject_key(["George W. Bush", "Bill Clinton"])
    right = ext._step_subject_key(["Bill Clinton", "George W. Bush"])
    assert left == right


def test_step_object_key_coalesces_surface_aliases_with_identity_row() -> None:
    row = {
        "title": "George W. Bush",
        "source": "wikilink",
        "resolver_hints": [
            {"lane": "sentence_link", "kind": "exact", "title": "George W. Bush", "score": 1.0}
        ],
    }
    object_row_by_key = {"bush": row, "george w bush": row}
    keys = ext._step_object_key(["Bush", "George W. Bush"], object_row_by_key)
    assert keys == ("george w bush",)
