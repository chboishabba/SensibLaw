from __future__ import annotations

from scripts import build_affidavit_coverage_review as builder
from src.policy.affidavit_lexical_heuristics import (
    LEXICAL_HEURISTIC_HINT_RULES,
    apply_lexical_heuristic_group,
    build_justification_packets,
)


def test_lexical_rule_inventory_is_quarantined_to_justification_group() -> None:
    assert set(LEXICAL_HEURISTIC_HINT_RULES) == {"justification"}


def test_apply_lexical_heuristic_group_returns_grouped_matches() -> None:
    excerpt = (
        "I acted with consent and only to address legal matters. "
        "The access was limited to specific purposes."
    )

    matches = apply_lexical_heuristic_group(excerpt, "justification")

    assert set(matches) == {"consent", "authority_or_necessity", "scope_limitation"}
    assert matches["consent"][0]["rule_id"] == "justification.consent"
    assert matches["authority_or_necessity"][0]["text"].lower() == "legal matters"
    assert matches["scope_limitation"][0]["text"].lower() in {"only to", "limited", "specific purposes"}


def test_build_justification_packets_uses_first_match_per_type() -> None:
    excerpt = "I acted with consent and with consent for specific purposes only to address care needs."

    packets = build_justification_packets(excerpt)

    assert [packet["type"] for packet in packets] == [
        "consent",
        "authority_or_necessity",
        "scope_limitation",
    ]
    assert packets[0]["rule_id"] == "justification.consent"
    assert packets[0]["span"]["text"].lower() == "consent"
    assert packets[1]["bound_response_span"]["text"].lower() in {"care"}


def test_builder_wrappers_delegate_to_shared_lexical_policy() -> None:
    excerpt = "I acted with consent for specific purposes."

    assert builder._apply_lexical_heuristic_group(excerpt, "justification") == apply_lexical_heuristic_group(
        excerpt,
        "justification",
    )
    assert builder._build_justification_packets(excerpt) == build_justification_packets(excerpt)
