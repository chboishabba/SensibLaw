from __future__ import annotations

import pytest

from src.policy.pruned_graph_preservation import (
    build_query_family_preservation_receipt,
    preservation_allows_absence,
)


def test_sound_only_pruned_artifact_cannot_support_absence() -> None:
    receipt = build_query_family_preservation_receipt(
        source_artifact_ref="wikidata:full",
        source_revision_ref="2026-03-09",
        pruned_artifact_ref="zelph:wikidata-pruned",
        pruned_revision_ref="2026-03-09-pruned",
        query_family_ref="query:p31-p279-type-closure",
        preservation_state="sound_only",
        soundness_receipt_ref="proof:compiled-to-source-mono",
        covered_relations=["P31", "P279"],
    )
    assert receipt["sound_for_positive_answers"] is True
    assert receipt["complete_for_negative_answers"] is False
    assert preservation_allows_absence(
        receipt, query_family_ref="query:p31-p279-type-closure"
    ) is False


def test_sound_and_complete_exact_family_can_support_absence() -> None:
    receipt = build_query_family_preservation_receipt(
        source_artifact_ref="wikidata:full",
        source_revision_ref="2026-03-09",
        pruned_artifact_ref="zelph:wikidata-pruned",
        pruned_revision_ref="2026-03-09-pruned",
        query_family_ref="query:p31-p279-type-closure",
        preservation_state="sound_and_complete",
        soundness_receipt_ref="proof:sound",
        completeness_receipt_ref="proof:complete",
        covered_relations=["P31", "P279"],
    )
    assert preservation_allows_absence(
        receipt, query_family_ref="query:p31-p279-type-closure"
    ) is True
    assert preservation_allows_absence(receipt, query_family_ref="query:p5991") is False


def test_completeness_receipt_cannot_be_attached_to_sound_only_state() -> None:
    with pytest.raises(ValueError, match="completeness_receipt_ref"):
        build_query_family_preservation_receipt(
            source_artifact_ref="wikidata:full",
            source_revision_ref="1",
            pruned_artifact_ref="zelph:pruned",
            pruned_revision_ref="1p",
            query_family_ref="query:test",
            preservation_state="sound_only",
            soundness_receipt_ref="proof:sound",
            completeness_receipt_ref="proof:complete",
        )
