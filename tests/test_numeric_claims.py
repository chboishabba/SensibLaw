from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from src.models.numeric_claims import (
    AnchorStatus,
    ClaimRelation,
    GraduationPolicy,
    Magnitude,
    MagnitudeUsage,
    RangeClaim,
    RatioClaim,
    authority_edges_for_quantified_claim,
    authority_edges_for_range_claim,
    authority_edges_for_ratio_claim,
    classify_claim_relation,
    graduate_magnitude_anchor,
    interval_from_sigfig,
    magnitude_id,
    make_quantified_claim,
    parse_surface_magnitude,
    significant_figures_from_surface,
)


@given(
    n=st.integers(min_value=-10**9, max_value=10**9),
    exp=st.integers(min_value=-4, max_value=4),
)
def test_magnitude_identity_invariant_under_decimal_rendering(n: int, exp: int) -> None:
    value = Decimal(n).scaleb(exp)
    assert magnitude_id(value, "usd") == magnitude_id(Decimal(str(value)), "usd")


@given(
    n=st.integers(min_value=-10**8, max_value=10**8).filter(lambda x: x != 0),
    exp=st.integers(min_value=-3, max_value=3),
    sig=st.integers(min_value=1, max_value=6),
)
def test_interval_contains_value(n: int, exp: int, sig: int) -> None:
    value = Decimal(n).scaleb(exp)
    lo, hi = interval_from_sigfig(value, sig)
    assert lo <= value <= hi


def test_parse_surface_magnitude_formatting_equivalence() -> None:
    a = parse_surface_magnitude("$1.2b")
    b = parse_surface_magnitude("1.20 billion", default_unit="usd")
    assert a is not None and b is not None
    assert a.id == b.id


def test_significant_figures_track_precision() -> None:
    assert significant_figures_from_surface("1.2b") == 2
    assert significant_figures_from_surface("1.20b") == 3


def test_claim_overlap_and_conflict_logic() -> None:
    mag = Magnitude(value=Decimal("1.2e9"), unit="usd", dimension="currency")
    c1 = make_quantified_claim(
        claim_id="c1",
        magnitude=mag,
        subject_id="profits",
        actor_id="a1",
        predicate="projected",
        time_scope="2007-Q1",
        modality="projection",
        significant_figures=2,
        source_event_id="ev1",
    )
    c2 = make_quantified_claim(
        claim_id="c2",
        magnitude=mag,
        subject_id="profits",
        actor_id="a2",
        predicate="reported",
        time_scope="2007-Q1",
        modality="reported",
        significant_figures=3,
        source_event_id="ev2",
    )
    assert classify_claim_relation(c1, c2) == ClaimRelation.EXACT

    mag_far = Magnitude(value=Decimal("1.5e9"), unit="usd", dimension="currency")
    c3 = make_quantified_claim(
        claim_id="c3",
        magnitude=mag_far,
        subject_id="profits",
        actor_id="a3",
        predicate="reported",
        time_scope="2007-Q1",
        modality="reported",
        significant_figures=4,
        source_event_id="ev3",
    )
    assert classify_claim_relation(c1, c3) == ClaimRelation.CONFLICT


def test_anchor_graduation_rules() -> None:
    policy = GraduationPolicy(recurrence_threshold=3, cross_actor_threshold=2)
    assert (
        graduate_magnitude_anchor(
            MagnitudeUsage(recurrence_count=3, cross_actor_count=2, boundary_usage_count=0, dimension="currency"),
            policy,
        )
        == AnchorStatus.ANCHOR
    )
    assert (
        graduate_magnitude_anchor(
            MagnitudeUsage(recurrence_count=2, cross_actor_count=1, boundary_usage_count=0, dimension="unknown"),
            policy,
        )
        == AnchorStatus.CANDIDATE
    )
    assert (
        graduate_magnitude_anchor(
            MagnitudeUsage(recurrence_count=1, cross_actor_count=1, boundary_usage_count=0, dimension="unknown"),
            policy,
        )
        == AnchorStatus.TRANSIENT
    )


def test_authority_edge_projection_shapes() -> None:
    mag = Magnitude(value=Decimal("68"), unit="percent", dimension="approval_percent")
    claim = make_quantified_claim(
        claim_id="qc1",
        magnitude=mag,
        subject_id="approval_rating",
        actor_id="george_w_bush",
        predicate="gained",
        time_scope="2001-09",
        modality="reported",
        significant_figures=2,
        source_event_id="ev0092",
    )
    qedges = authority_edges_for_quantified_claim(claim)
    assert any(e.predicate == "quantified_by" and e.dst == mag.id for e in qedges)

    rclaim = RangeClaim(
        id="rc1",
        lower_magnitude_id="mag:1.2e9|usd",
        upper_magnitude_id="mag:1.7e9|usd",
        subject_id="profits",
        actor_id="issuer",
        predicate="projected",
        time_scope="2007-Q1",
        modality="projection",
        source_event_id="evx",
    )
    redges = authority_edges_for_range_claim(rclaim)
    assert any(e.predicate == "lower_bound" for e in redges)
    assert any(e.predicate == "upper_bound" for e in redges)

    ratio = RatioClaim(
        id="rr1",
        numerator_magnitude_id="mag:18|",
        denominator_magnitude_id="mag:21|",
        subject_id="countries_surveyed",
        actor_id="pollster",
        predicate="found",
        time_scope="2006",
        source_event_id="ev0097",
    )
    ratio_edges = authority_edges_for_ratio_claim(ratio)
    assert any(e.predicate == "numerator" for e in ratio_edges)
    assert any(e.predicate == "denominator" for e in ratio_edges)
