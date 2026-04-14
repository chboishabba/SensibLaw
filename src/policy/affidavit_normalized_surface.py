"""Normalized facade over affidavit policy helpers.

This groups the current affidavit-local helper modules into a stable import
surface without changing behavior or forcing immediate renames.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.policy.affidavit_candidate_alignment import (
    family_alignment_adjustment,
    is_quote_rebuttal_support_excerpt,
    predicate_alignment_score,
)
from src.policy.affidavit_candidate_arbitration import (
    arbitrate_candidate_selection,
    candidate_rank_key,
    clause_rank_key,
    finalize_candidate_selection,
    preserve_duplicate_match_excerpt,
    promote_clause_alternate,
    promote_duplicate_root_alternate,
    promote_non_echo_alternate,
    resolve_duplicate_match_excerpt,
    select_best_candidate,
)
from src.policy.affidavit_claim_root import (
    derive_claim_root_fields,
    is_duplicate_response_excerpt,
    normalize_claim_root_text,
    stable_claim_root_id,
)
from src.policy.affidavit_extraction_hints import (
    DEFAULT_WORKLOAD_CLASS_PRIORITY,
    MONTH_PATTERN,
    PROCEDURAL_EVENT_KEYWORDS,
    build_candidate_anchors,
    build_provisional_anchor_bundles,
    build_provisional_structured_anchors,
    classify_workload_with_hints,
    extract_extraction_hints,
    recommend_next_action,
)
from src.policy.affidavit_lexical_heuristics import (
    LEXICAL_HEURISTIC_HINT_RULES,
    apply_lexical_heuristic_group,
    build_justification_packets,
)
from src.policy.affidavit_response_semantics import (
    derive_claim_state,
    derive_missing_dimensions,
    derive_primary_target_component,
    derive_relation_classification,
    derive_semantic_basis,
    infer_response_packet,
)
from src.policy.affidavit_structural_sentence import analyze_structural_sentence
from src.policy.affidavit_text_normalization import (
    find_numbered_rebuttal_start,
    is_duplicate_response_excerpt,
    predicate_focus_tokens,
    split_affidavit_sentence_clauses,
    split_affidavit_text,
)
from src.text.shared_text_normalization import (
    split_text_clauses,
    split_text_segments,
    tokenize_canonical_text,
)

text = SimpleNamespace(
    find_numbered_rebuttal_start=find_numbered_rebuttal_start,
    is_duplicate_response_excerpt=is_duplicate_response_excerpt,
    predicate_focus_tokens=predicate_focus_tokens,
    split_affidavit_sentence_clauses=split_affidavit_sentence_clauses,
    split_source_segment_clauses=split_text_clauses,
    split_source_text_segments=split_text_segments,
    split_affidavit_text=split_affidavit_text,
    tokenize_affidavit_text=tokenize_canonical_text,
)

matching = SimpleNamespace(
    arbitrate_candidate_selection=arbitrate_candidate_selection,
    candidate_rank_key=candidate_rank_key,
    clause_rank_key=clause_rank_key,
    derive_claim_root_fields=derive_claim_root_fields,
    family_alignment_adjustment=family_alignment_adjustment,
    finalize_candidate_selection=finalize_candidate_selection,
    is_duplicate_response_excerpt=is_duplicate_response_excerpt,
    is_quote_rebuttal_support_excerpt=is_quote_rebuttal_support_excerpt,
    normalize_claim_root_text=normalize_claim_root_text,
    predicate_alignment_score=predicate_alignment_score,
    preserve_duplicate_match_excerpt=preserve_duplicate_match_excerpt,
    promote_clause_alternate=promote_clause_alternate,
    promote_duplicate_root_alternate=promote_duplicate_root_alternate,
    promote_non_echo_alternate=promote_non_echo_alternate,
    resolve_duplicate_match_excerpt=resolve_duplicate_match_excerpt,
    select_best_candidate=select_best_candidate,
    stable_claim_root_id=stable_claim_root_id,
)

semantics = SimpleNamespace(
    LEXICAL_HEURISTIC_HINT_RULES=LEXICAL_HEURISTIC_HINT_RULES,
    apply_lexical_heuristic_group=apply_lexical_heuristic_group,
    build_justification_packets=build_justification_packets,
    derive_claim_state=derive_claim_state,
    derive_missing_dimensions=derive_missing_dimensions,
    derive_primary_target_component=derive_primary_target_component,
    derive_relation_classification=derive_relation_classification,
    derive_semantic_basis=derive_semantic_basis,
    infer_response_packet=infer_response_packet,
)

review_hints = SimpleNamespace(
    DEFAULT_WORKLOAD_CLASS_PRIORITY=DEFAULT_WORKLOAD_CLASS_PRIORITY,
    MONTH_PATTERN=MONTH_PATTERN,
    PROCEDURAL_EVENT_KEYWORDS=PROCEDURAL_EVENT_KEYWORDS,
    build_candidate_anchors=build_candidate_anchors,
    build_provisional_anchor_bundles=build_provisional_anchor_bundles,
    build_provisional_structured_anchors=build_provisional_structured_anchors,
    classify_workload_with_hints=classify_workload_with_hints,
    extract_extraction_hints=extract_extraction_hints,
    recommend_next_action=recommend_next_action,
)

structural = SimpleNamespace(
    analyze_structural_sentence=analyze_structural_sentence,
)

__all__ = [
    "matching",
    "review_hints",
    "semantics",
    "structural",
    "text",
]
