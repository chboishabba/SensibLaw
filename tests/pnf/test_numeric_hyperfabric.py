from __future__ import annotations

import pytest

from src.pnf.numeric_hyperfabric import (
    MdlProfile,
    PromotionEvidence,
    RegionMeasure,
    active_cardinality_decreases,
    ancestor_powers,
    bounded_segmentation,
    compression_gain,
    numeric_digest,
    should_promote,
    symbol_digest,
    SymbolKind,
)


def test_numeric_identity_rejects_text_after_interning_boundary() -> None:
    assert numeric_digest(1, 2, (3, 4)) == numeric_digest(1, 2, (3, 4))
    assert numeric_digest(1, 2, (3, 4)) != numeric_digest(1, 2, (4, 3))
    with pytest.raises(TypeError, match="numeric graph identity"):
        numeric_digest("not-interned")


def test_symbol_digest_is_the_single_lexical_boundary() -> None:
    first = symbol_digest(SymbolKind.LEMMA, "obligation")
    second = symbol_digest(SymbolKind.LEMMA, "obligation")
    different_kind = symbol_digest(SymbolKind.ORTH, "obligation")
    assert len(first) == 32
    assert first == second
    assert first != different_kind


def test_promotion_requires_information_beyond_carrying_and_ambiguity_cost() -> None:
    profile = MdlProfile(promotion_threshold=1.0)
    weak = PromotionEvidence(
        information_gain=1.0,
        representation_cost=1.0,
        ambiguity_cost=1.0,
    )
    outward = PromotionEvidence(
        information_gain=1.0,
        representation_cost=1.0,
        ambiguity_cost=1.0,
        factor_participation=1,
        outward_demand_count=1,
    )
    assert not should_promote(weak, profile)
    assert should_promote(outward, profile)


def test_bounded_segmentation_has_linear_bound_for_fixed_window_and_beam() -> None:
    profile = MdlProfile(max_window=4, beam_width=3)
    measures = tuple(
        RegionMeasure(
            node_count=5,
            edge_count=4,
            boundary_demand_weight=float(index % 2),
            interface_cardinality=2,
        )
        for index in range(100)
    )
    result = bounded_segmentation(measures, profile=profile)
    assert result.segments
    assert result.evaluated_candidates <= result.asymptotic_bound
    assert result.asymptotic_bound == 100 * 4 * 3


def test_compression_gain_rewards_smaller_merged_interface() -> None:
    profile = MdlProfile()
    left = RegionMeasure(node_count=5, edge_count=4, interface_cardinality=4)
    right = RegionMeasure(node_count=5, edge_count=4, interface_cardinality=4)
    merged = RegionMeasure(node_count=7, edge_count=6, interface_cardinality=3)
    assert compression_gain(left, right, merged, 2.0, profile) > 0


def test_binary_lifting_and_active_cardinality_contracts() -> None:
    assert ancestor_powers(13) == (3, 2, 0)
    assert active_cardinality_decreases((1000, 300, 300, 40, 4))
    assert not active_cardinality_decreases((10, 11))
