"""Utilities for case comparison and distinction."""

from .engine import (
    CaseSilhouette,
    extract_case_silhouette,
    extract_holding_and_facts,
    compare_cases,
    compare_story_to_case,
)
from .factor_packs import factor_pack_for_case, distinguish_story

from .loader import load_case_silhouette

__all__ = [
    "CaseSilhouette",
    "extract_case_silhouette",
    "extract_holding_and_facts",
    "compare_cases",
    "factor_pack_for_case",
    "distinguish_story",
    "compare_story_to_case",
    "load_case_silhouette",
]
