"""Shared affidavit response semantics helpers."""
from __future__ import annotations

from typing import Any, Mapping


def infer_response_packet(
    *,
    proposition_text: str,
    best_match_excerpt: str,
    duplicate_match_excerpt: str | None,
    response_role: str | None,
    coverage_status: str,
    characterization_terms: set[str] | frozenset[str],
    justification_matches: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    role = str(response_role or "").strip()
    excerpt = str(best_match_excerpt or "").strip()
    duplicate_excerpt = str(duplicate_match_excerpt or "").strip() or None
    proposition_lower = proposition_text.casefold()
    excerpt_lower = excerpt.casefold()
    response_acts: list[str] = []
    legal_significance_signals: list[str] = []

    if duplicate_excerpt:
        response_acts.append("repetition_only")
    characterization_overlap = any(term in proposition_lower and term in excerpt_lower for term in characterization_terms)
    characterization_dispute = characterization_overlap or "characterization" in excerpt_lower
    if role in {"dispute", "hedged_denial"}:
        if characterization_dispute:
            response_acts.append("deny_characterisation")
            legal_significance_signals.append("characterization_dispute")
        else:
            response_acts.append("deny_fact")
            legal_significance_signals.append("factual_denial")
        if role == "hedged_denial":
            response_acts.append("hedged_denial")
            legal_significance_signals.append("hedged_denial_signal")
    elif role == "admission":
        response_acts.append("admit_fact")
        legal_significance_signals.append("factual_admission")
    elif role == "explanation":
        response_acts.append("explain_context")
        legal_significance_signals.append("context_explanation")
    elif role == "support_or_corroboration":
        response_acts.append("corroborate_or_ground")
        legal_significance_signals.append("evidentiary_grounding_signal")
    elif role == "non_response":
        response_acts.append("non_response")
    elif role == "restatement_only":
        response_acts.append("repetition_only")
    elif role == "procedural_frame":
        response_acts.append("procedural_or_nonresponsive_frame")

    if justification_matches.get("consent"):
        response_acts.append("justify")
        legal_significance_signals.append("consent_signal")
    if justification_matches.get("authority_or_necessity"):
        legal_significance_signals.append("authority_or_necessity_signal")
    if justification_matches.get("scope_limitation"):
        response_acts.append("scope_limitation")
        legal_significance_signals.append("scope_limitation")

    if coverage_status == "covered" and response_acts and all(act != "repetition_only" for act in response_acts):
        support_status = "substantively_addressed"
    elif coverage_status == "partial" and duplicate_excerpt:
        support_status = "textually_addressed"
    elif coverage_status == "partial" and response_acts:
        support_status = "responsive_but_non_substantive"
    elif coverage_status in {"unsupported_affidavit", "contested_source", "abstained_source"}:
        support_status = "unresolved"
    else:
        support_status = "textually_addressed"

    if "evidentiary_grounding_signal" in legal_significance_signals and support_status in {
        "substantively_addressed",
        "responsive_but_non_substantive",
    }:
        support_status = "evidentially_grounded_response"

    return {
        "response_acts": sorted(dict.fromkeys(response_acts)),
        "legal_significance_signals": sorted(dict.fromkeys(legal_significance_signals)),
        "support_status": support_status,
    }


def derive_primary_target_component(*, response: Mapping[str, Any], response_acts: list[str]) -> str:
    component_targets = response.get("component_targets") if isinstance(response.get("component_targets"), list) else []
    normalized_targets = [str(target).strip() for target in component_targets if str(target).strip()]
    if "characterization" in normalized_targets and "deny_characterisation" in set(response_acts):
        return "characterization"
    if "time" in normalized_targets:
        return "time"
    if "predicate_text" in normalized_targets:
        return "predicate_text"
    return normalized_targets[0] if normalized_targets else "predicate_text"


def derive_semantic_basis(
    *,
    response_cues: list[str],
    response: Mapping[str, Any],
    response_component_bindings: list[dict[str, Any]],
    justifications: list[dict[str, Any]],
) -> str:
    if any(str(cue).startswith("structural:") for cue in response_cues):
        return "structural"
    structural_binding_components = {
        str(binding.get("component") or "").strip()
        for binding in response_component_bindings
        if isinstance(binding, Mapping)
        and str(binding.get("component") or "").strip() in {"predicate_text", "characterization", "time"}
    }
    if structural_binding_components and justifications:
        return "mixed"
    if structural_binding_components:
        return "structural"
    if justifications:
        return "heuristic"
    speech_act = str(response.get("speech_act") or "").strip()
    if speech_act in {"deny", "admit", "explain"}:
        return "heuristic"
    return "heuristic"


def derive_claim_state(
    *,
    response_acts: list[str],
    legal_significance_signals: list[str],
    support_status: str,
    duplicate_match_excerpt: str | None,
) -> dict[str, str]:
    acts = set(response_acts)
    signals = set(legal_significance_signals)
    has_for = bool(
        {"admit_fact", "corroborate_or_ground"} & acts
        or {"factual_admission", "evidentiary_grounding_signal"} & signals
    )
    has_against = bool(
        {"deny_fact", "deny_characterisation", "hedged_denial"} & acts
        or {"factual_denial", "characterization_dispute", "hedged_denial_signal"} & signals
    )
    if has_for and has_against:
        support_direction = "mixed"
    elif has_for:
        support_direction = "for"
    elif has_against:
        support_direction = "against"
    else:
        support_direction = "none"

    if support_status == "unresolved" and support_direction == "none":
        conflict_state = "unanswered"
    elif support_direction == "mixed":
        conflict_state = "partially_reconciled"
    elif support_direction == "against":
        conflict_state = "disputed"
    elif support_direction == "for":
        conflict_state = "undisputed"
    elif duplicate_match_excerpt:
        conflict_state = "unresolved"
    else:
        conflict_state = "unanswered"

    if support_status == "evidentially_grounded_response":
        evidentiary_state = "supported"
    elif support_status == "substantively_addressed" and support_direction in {"for", "mixed"}:
        evidentiary_state = "weakly_supported"
    elif support_direction == "against":
        evidentiary_state = "unproven"
    elif support_status in {"textually_addressed", "responsive_but_non_substantive", "unresolved"}:
        evidentiary_state = "unproven"
    else:
        evidentiary_state = "unassessed"

    if support_direction == "none" and support_status == "unresolved":
        operational_status = "claim_only"
    elif support_direction == "for" and conflict_state == "undisputed" and evidentiary_state in {"unproven", "weakly_supported"}:
        operational_status = "claim_with_support"
    elif support_direction == "against":
        operational_status = "claim_with_opposition" if conflict_state == "unanswered" else "disputed_claim"
    elif support_direction == "mixed" and conflict_state == "partially_reconciled":
        operational_status = "partially_reconciled_claim"
    elif support_direction == "for" and evidentiary_state in {"supported", "strongly_supported"}:
        operational_status = "resolved_but_unproven"
    else:
        operational_status = "disputed_claim" if conflict_state == "disputed" else "claim_only"

    return {
        "support_direction": support_direction,
        "conflict_state": conflict_state,
        "evidentiary_state": evidentiary_state,
        "operational_status": operational_status,
    }


def derive_missing_dimensions(
    *,
    coverage_status: str,
    support_status: str,
    primary_target_component: str | None,
    best_match_excerpt: str | None,
    duplicate_match_excerpt: str | None,
) -> list[str]:
    dimensions: list[str] = []
    component = str(primary_target_component or "").strip()
    if component == "time":
        dimensions.append("time")
    elif component == "characterization":
        dimensions.append("direct_response")
    elif component == "predicate_text":
        dimensions.append("action")

    if support_status in {"responsive_but_non_substantive", "unresolved"}:
        dimensions.append("direct_response")
    if support_status == "textually_addressed" and not str(duplicate_match_excerpt or "").strip():
        dimensions.append("object")
    if coverage_status == "unsupported_affidavit" and not str(best_match_excerpt or "").strip():
        dimensions.append("direct_response")

    deduped: list[str] = []
    for dimension in dimensions:
        if dimension and dimension not in deduped:
            deduped.append(dimension)
    return deduped or ["direct_response"]


def derive_relation_classification(
    *,
    coverage_status: str,
    support_status: str,
    conflict_state: str,
    support_direction: str,
    best_response_role: str | None,
    primary_target_component: str | None,
    best_match_excerpt: str | None,
    duplicate_match_excerpt: str | None,
    alternate_context_excerpt: str | None = None,
) -> dict[str, Any]:
    role = str(best_response_role or "").strip()
    component = str(primary_target_component or "").strip()
    missing_dimensions = derive_missing_dimensions(
        coverage_status=coverage_status,
        support_status=support_status,
        primary_target_component=component,
        best_match_excerpt=best_match_excerpt,
        duplicate_match_excerpt=duplicate_match_excerpt,
    )

    relation_root = "non_resolving"
    relation_leaf = "non_substantive_response"
    classification = "non_substantive_response"
    reason = "The matched response is procedural, explanatory, or otherwise non-substantive for this proposition."
    matched_response = str(best_match_excerpt or "").strip() or None

    if str(duplicate_match_excerpt or "").strip():
        relation_root = "supports"
        relation_leaf = "equivalent_support"
        classification = "supported"
        matched_response = str(duplicate_match_excerpt or "").strip() or matched_response
        if str(alternate_context_excerpt or "").strip():
            reason = "A direct or near-duplicate clause supports the same claim root, while a nearby alternate clause adds context and should not replace the matching leaf."
        else:
            reason = "A direct or near-duplicate clause supports the same claim root."
        missing_dimensions = []
    elif coverage_status == "covered":
        relation_root = "supports"
        relation_leaf = "exact_support" if support_status == "substantively_addressed" else "equivalent_support"
        classification = "supported"
        reason = "The matched response aligns on the same proposition with substantive support."
    elif coverage_status in {"contested_source", "contested_affidavit"} or conflict_state == "disputed" or support_direction == "against" or role == "dispute":
        relation_root = "invalidates"
        relation_leaf = "explicit_dispute" if role in {"dispute", "hedged_denial"} else "implicit_dispute"
        classification = "disputed"
        reason = "The matched response disputes or materially opposes the same proposition."
    elif coverage_status == "unsupported_affidavit":
        relation_root = "unanswered"
        relation_leaf = "missing"
        classification = "missing"
        reason = "No adequately aligned response row was found for this proposition."
    elif support_status == "evidentially_grounded_response" or role == "admission":
        relation_root = "supports"
        relation_leaf = "partial_support"
        classification = "partial_support"
        reason = "The matched response grounds part of the proposition, but does not fully resolve it."
    elif component == "time":
        relation_root = "non_resolving"
        relation_leaf = "adjacent_event"
        classification = "adjacent_event"
        reason = "The matched response appears to concern a nearby event or timing slice rather than the exact proposition."
    elif support_status == "textually_addressed":
        relation_root = "non_resolving"
        relation_leaf = "substitution"
        classification = "substitution"
        reason = "The matched response overlaps lexically, but substitutes a different act or incident."
    elif support_status in {"textually_addressed", "responsive_but_non_substantive", "evidentially_grounded_response"} or role in {"explanation", "procedural_frame", "restatement_only", "non_response"}:
        relation_root = "non_resolving"
        relation_leaf = "non_substantive_response"
        classification = "non_substantive_response"
        reason = "The matched response is procedural, explanatory, or otherwise non-substantive for this proposition."
    elif coverage_status == "partial":
        relation_root = "supports"
        relation_leaf = "partial_support"
        classification = "partial_support"
        reason = "The matched response partially overlaps the proposition but leaves key dimensions unresolved."

    return {
        "relation_root": relation_root,
        "relation_leaf": relation_leaf,
        "classification": classification,
        "explanation": {
            "classification": classification,
            "matched_response": matched_response,
            "reason": reason,
            "missing_dimension": missing_dimensions,
        },
        "missing_dimensions": missing_dimensions,
    }


__all__ = [
    "derive_claim_state",
    "derive_missing_dimensions",
    "derive_primary_target_component",
    "derive_relation_classification",
    "derive_semantic_basis",
    "infer_response_packet",
]
