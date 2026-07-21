"""Generic algebra for branch-preserving semantic compilation."""

from .alternatives import TypedAlternative
from .constraints import ConstraintAssessment
from .factors import Factor, FactorConstraint
from .meets import MeetState, TypedMeet
from .pressures import PressureAssessment, PressureKind
from .refinements import FactorRefinement, ResidualTransition
from .revision_identity import (
    canonicalize_factor_revision,
    computed_factor_revision_ref,
    factor_revision_payload,
    factor_revision_ref,
    strip_factor_revision_ref,
)

__all__ = [
    "ConstraintAssessment",
    "Factor",
    "FactorConstraint",
    "FactorRefinement",
    "MeetState",
    "PressureAssessment",
    "PressureKind",
    "ResidualTransition",
    "TypedAlternative",
    "TypedMeet",
    "canonicalize_factor_revision",
    "computed_factor_revision_ref",
    "factor_revision_payload",
    "factor_revision_ref",
    "strip_factor_revision_ref",
]
