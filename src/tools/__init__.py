"""Helper utilities for SensibLaw tools."""

from .glossary import as_table, load_glossary, lookup, rewrite_text, TermRewriter
from .ego_contest import (
    BATNASheet,
    EgoContestReport,
    OfferSummary,
    ToneAuditResult,
    ToneFlag,
    build_batna_sheet,
    generate_cooling_off_macros,
    normalise_offers,
    run_ego_contest_kit,
    side_by_side_diff,
    tone_audit,
)

__all__ = [
    "load_glossary",
    "lookup",
    "as_table",
    "rewrite_text",
    "TermRewriter",
    "BATNASheet",
    "EgoContestReport",
    "OfferSummary",
    "ToneAuditResult",
    "ToneFlag",
    "build_batna_sheet",
    "generate_cooling_off_macros",
    "normalise_offers",
    "run_ego_contest_kit",
    "side_by_side_diff",
    "tone_audit",
]
