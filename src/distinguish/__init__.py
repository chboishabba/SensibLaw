"""Utilities for case comparison and distinction."""

from .engine import (
    CaseSilhouette,
    extract_case_silhouette,
    extract_holding_and_facts,
    compare_cases,
)
from .factor_packs import factor_pack_for_case, distinguish_story

__all__ = [
    "CaseSilhouette",
    "extract_case_silhouette",
    "extract_holding_and_facts",
    "compare_cases",
    "factor_pack_for_case",
    "distinguish_story",
]
