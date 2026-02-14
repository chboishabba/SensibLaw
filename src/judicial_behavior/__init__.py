"""Descriptive-only decision outcome aggregation (non-authoritative).

This package intentionally does not perform prediction or scoring. It provides
deterministic summary statistics over explicit case observations.
"""

from .model import CaseObservation, OutcomeLabel
from .stats import (
    aggregate_outcomes,
    aggregate_beta_binomial,
    aggregate_gamma_poisson,
    aggregate_ridge_logistic_map,
    aggregate_lognormal_tail,
)
from .gamma import gamma_poisson_posterior
from .logistic import build_sparse_binary_design, fit_ridge_logistic_map

__all__ = [
    "CaseObservation",
    "OutcomeLabel",
    "aggregate_outcomes",
    "aggregate_beta_binomial",
    "aggregate_gamma_poisson",
    "aggregate_ridge_logistic_map",
    "aggregate_lognormal_tail",
    "gamma_poisson_posterior",
    "build_sparse_binary_design",
    "fit_ridge_logistic_map",
]
