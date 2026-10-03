"""Stable GOV-1 facade over existing SensibLaw policy ownership.

This module is intentionally additive: it does not alter the legacy policy
initializer or create a new semantic/review authority.
"""

from .control_case import (
    CONTROL_CASE_SCHEMA_VERSION,
    EVIDENCE_STATES,
    GOV1_PROFILE_ID,
    SERVICE_CHANGE_STATES,
    build_control_case,
)
from .control_evaluator import evaluate_control_profile
from .control_profiles import GOV1_INTEGRATED_PROFILE, get_control_profile
from .information_governance import (
    INFORMATION_ASSET_SCHEMA_VERSION,
    PROCESSING_ACTIVITY_SCHEMA_VERSION,
    build_information_asset,
    build_processing_activity,
)
from .nonconformance import (
    CAPA_SCHEMA_VERSION,
    DEFECT_KINDS,
    NONCONFORMANCE_SCHEMA_VERSION,
    build_capa_cycle,
    build_nonconformance,
)

__all__ = [
    "CONTROL_CASE_SCHEMA_VERSION",
    "EVIDENCE_STATES",
    "GOV1_PROFILE_ID",
    "GOV1_INTEGRATED_PROFILE",
    "SERVICE_CHANGE_STATES",
    "INFORMATION_ASSET_SCHEMA_VERSION",
    "PROCESSING_ACTIVITY_SCHEMA_VERSION",
    "NONCONFORMANCE_SCHEMA_VERSION",
    "CAPA_SCHEMA_VERSION",
    "DEFECT_KINDS",
    "get_control_profile",
    "evaluate_control_profile",
    "build_control_case",
    "build_information_asset",
    "build_processing_activity",
    "build_nonconformance",
    "build_capa_cycle",
]
