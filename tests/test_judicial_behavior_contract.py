import pytest

from src.judicial_behavior.model import CaseObservation
from src.judicial_behavior.bayes import beta_cdf, beta_ppf
from src.judicial_behavior.stats import (
    IndividualStatsDisabledError,
    SliceDeclarationError,
    aggregate_beta_binomial,
    aggregate_outcomes,
    aggregate_ridge_logistic_map,
    aggregate_lognormal_tail,
)


def test_aggregate_is_order_independent():
    a = CaseObservation(
        case_id="c1",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        wrong_type_id="negligence",
        outcome="plaintiff",
    )
    b = CaseObservation(
        case_id="c2",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        wrong_type_id="negligence",
        outcome="defendant",
    )
    c = CaseObservation(
        case_id="c3",
        jurisdiction_id="AU-VIC",
        court_id="VSC",
        court_level="trial",
        wrong_type_id="defamation",
        outcome="defendant",
    )

    slice_decl = {"filters": {}, "group_by": ["jurisdiction_id", "court_id", "court_level"], "time_bounds_declared": {"start": None, "end": None}}
    out1 = aggregate_outcomes([a, b, c], slice=slice_decl)
    out2 = aggregate_outcomes([c, b, a], slice=slice_decl)
    assert out1 == out2
    assert out1["corpus"]["n_total"] == 3
    assert "interpretation_guard" in out1


def test_individual_level_grouping_is_disabled_by_default():
    a = CaseObservation(
        case_id="c1",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        judge_id="J:Smith",
        outcome="plaintiff",
    )
    with pytest.raises(IndividualStatsDisabledError):
        aggregate_outcomes(
            [a],
            group_by=("judge_id",),
            slice={"filters": {}, "group_by": ["judge_id"], "time_bounds_declared": {"start": None, "end": None}},
        )


def test_individual_level_grouping_requires_opt_in():
    a = CaseObservation(
        case_id="c1",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        judge_id="J:Smith",
        outcome="plaintiff",
    )
    out = aggregate_outcomes(
        [a],
        group_by=("judge_id",),
        allow_individuals=True,
        slice={"filters": {}, "group_by": ["judge_id"], "time_bounds_declared": {"start": None, "end": None}},
    )
    assert out["allow_individuals"] is True
    assert out["groups"][0]["outcomes"]["plaintiff"] == 1


def test_slice_declaration_is_required():
    a = CaseObservation(case_id="c1", jurisdiction_id="AU-NSW", court_id="NSWSC", court_level="trial", outcome="plaintiff")
    with pytest.raises(SliceDeclarationError):
        aggregate_outcomes([a])
    with pytest.raises(SliceDeclarationError):
        aggregate_outcomes([a], slice={"filters": {}, "group_by": ["wrong"], "time_bounds_declared": {"start": None, "end": None}})


def test_beta_cdf_basic_uniform():
    # Beta(1,1) is uniform -> CDF(x)=x
    assert abs(beta_cdf(0.25, 1.0, 1.0) - 0.25) < 1e-10
    assert abs(beta_cdf(0.5, 1.0, 1.0) - 0.5) < 1e-10


def test_beta_ppf_basic_uniform():
    assert abs(beta_ppf(0.25, 1.0, 1.0) - 0.25) < 5e-10
    assert abs(beta_ppf(0.5, 1.0, 1.0) - 0.5) < 5e-10


def test_beta_binomial_aggregate_is_order_independent():
    a = CaseObservation(
        case_id="c1",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        wrong_type_id="negligence",
        outcome="plaintiff",
    )
    b = CaseObservation(
        case_id="c2",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        wrong_type_id="negligence",
        outcome="defendant",
    )
    c = CaseObservation(
        case_id="c3",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        wrong_type_id="negligence",
        outcome="plaintiff",
    )
    slice_decl = {"filters": {}, "group_by": ["jurisdiction_id", "court_id", "court_level"], "time_bounds_declared": {"start": None, "end": None}}
    out1 = aggregate_beta_binomial([a, b, c], kappa=10.0, slice=slice_decl)
    out2 = aggregate_beta_binomial([c, b, a], kappa=10.0, slice=slice_decl)
    assert out1 == out2
    assert out1["corpus"]["n_total"] == 3


def test_ridge_logistic_requires_slice_declaration_and_is_deterministic():
    a = CaseObservation(
        case_id="c1",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        wrong_type_id="negligence",
        predicate_keys=("neg.duty_found", "cla.s5b_applied"),
        outcome="plaintiff",
    )
    b = CaseObservation(
        case_id="c2",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        wrong_type_id="negligence",
        predicate_keys=("cla.s5b_applied",),
        outcome="defendant",
    )
    slice_decl = {"filters": {}, "group_by": ["jurisdiction_id", "court_id", "court_level"], "time_bounds_declared": {"start": None, "end": None}}
    with pytest.raises(SliceDeclarationError):
        aggregate_ridge_logistic_map([a, b])
    out1 = aggregate_ridge_logistic_map([a, b], slice=slice_decl, max_features=50, max_iter=10)
    out2 = aggregate_ridge_logistic_map([b, a], slice=slice_decl, max_features=50, max_iter=10)
    assert out1 == out2
    assert out1["mode"] == "descriptive_only"
    assert "interpretation_guard" in out1
    assert out1["corpus"]["n_total"] == 2


def test_lognormal_tail_requires_slice_declaration_and_is_deterministic():
    a = CaseObservation(
        case_id="c1",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        decision_date="2020-01-01",
        outcome="plaintiff",
    )
    b = CaseObservation(
        case_id="c2",
        jurisdiction_id="AU-NSW",
        court_id="NSWSC",
        court_level="trial",
        decision_date="2020-06-01",
        outcome="defendant",
    )
    slice_decl = {"filters": {}, "group_by": ["jurisdiction_id", "court_id", "court_level"], "time_bounds_declared": {"start": "2020-01-01", "end": "2020-12-31"}}
    with pytest.raises(SliceDeclarationError):
        aggregate_lognormal_tail([(a, 100.0), (b, 200.0)])
    out1 = aggregate_lognormal_tail([(a, 100.0), (b, 200.0)], slice=slice_decl, threshold=150.0)
    out2 = aggregate_lognormal_tail([(b, 200.0), (a, 100.0)], slice=slice_decl, threshold=150.0)
    assert out1 == out2
    assert out1["method"] == "lognormal_tail"
    assert out1["corpus"]["n_total"] == 2
    assert out1["corpus"]["time_min"] == "2020-01-01"
    assert out1["corpus"]["time_max"] == "2020-06-01"
