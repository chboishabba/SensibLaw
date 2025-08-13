"""Utilities for case comparison and distinction."""

from .engine import (
    CaseSilhouette,
    extract_case_silhouette,
    extract_holding_and_facts,
    compare_cases,
)

__all__ = [
    "CaseSilhouette",
    "extract_case_silhouette",
    "extract_holding_and_facts",
    "compare_cases",
]
