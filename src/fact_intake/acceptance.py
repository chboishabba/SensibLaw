from __future__ import annotations

from typing import Any, Callable, Mapping


FACT_REVIEW_ACCEPTANCE_VERSION = "fact.review.acceptance.v1"
FACT_REVIEW_ACCEPTANCE_BATCH_VERSION = "fact.review.acceptance.batch.v1"


def _has_provenance_links(workbench: Mapping[str, Any]) -> bool:
    facts = workbench.get("facts")
    if not isinstance(facts, list) or not facts:
        return False
    return all(
        bool(row.get("statement_ids")) and bool(row.get("source_ids"))
        for row in facts
        if isinstance(row, Mapping)
    )


def _has_review_queue(workbench: Mapping[str, Any]) -> bool:
    queue = workbench.get("review_queue")
    return isinstance(queue, list) and len(queue) > 0


def _has_chronology_split(workbench: Mapping[str, Any]) -> bool:
    groups = workbench.get("chronology_groups")
    return isinstance(groups, Mapping) and {"dated_events", "undated_events", "facts_with_no_event"} <= set(groups.keys())


def _has_contested_summary(workbench: Mapping[str, Any]) -> bool:
    summary = workbench.get("contested_summary")
    return isinstance(summary, Mapping) and "count" in summary and "items" in summary


def _has_workflow_link(workbench: Mapping[str, Any]) -> bool:
    run = workbench.get("run")
    return isinstance(run, Mapping) and isinstance(run.get("workflow_link"), Mapping)


def _has_reopen_navigation(workbench: Mapping[str, Any]) -> bool:
    navigation = workbench.get("reopen_navigation")
    if not isinstance(navigation, Mapping):
        return False
    current = navigation.get("current")
    recent_sources = navigation.get("recent_sources")
    query = navigation.get("query")
    return (
        isinstance(current, Mapping)
        and bool(current.get("workflow_kind"))
        and isinstance(query, Mapping)
        and isinstance(recent_sources, list)
        and len(recent_sources) > 0
    )


def _has_legal_procedural_signal(workbench: Mapping[str, Any]) -> bool:
    queue = workbench.get("review_queue")
    if not isinstance(queue, list):
        return False
    return any(bool(row.get("has_legal_procedural_observations")) for row in queue if isinstance(row, Mapping))


def _has_assertion_outcome_distinction(workbench: Mapping[str, Any]) -> bool:
    facts = workbench.get("facts")
    if not isinstance(facts, list) or not facts:
        return False
    return any(
        bool(row.get("signal_classes")) and (
            "party_assertion" in set(row.get("signal_classes", []))
            or "procedural_outcome" in set(row.get("signal_classes", []))
            or "later_annotation" in set(row.get("source_signal_classes", []))
        )
        for row in facts
        if isinstance(row, Mapping)
    )


def _has_roleful_queue_reasons(workbench: Mapping[str, Any]) -> bool:
    queue = workbench.get("review_queue")
    if not isinstance(queue, list) or not queue:
        return False
    roleful = {"missing_date", "missing_actor", "contradictory_chronology", "statement_only_fact", "procedural_significance"}
    return any(roleful & set(row.get("reason_codes", [])) for row in queue if isinstance(row, Mapping))


def _is_read_only_posture(workbench: Mapping[str, Any]) -> bool:
    return bool(workbench.get("operator_views")) and "facts" in workbench and "events" in workbench


def _supports_sparse_chronology(workbench: Mapping[str, Any]) -> bool:
    groups = workbench.get("chronology_groups")
    if not isinstance(groups, Mapping):
        return False
    return "undated_events" in groups and "contested_chronology_items" in groups


def _has_approximate_chronology(workbench: Mapping[str, Any]) -> bool:
    groups = workbench.get("chronology_groups")
    if not isinstance(groups, Mapping):
        return False
    return "approximate_events" in groups


def _has_queue_grouping(workbench: Mapping[str, Any]) -> bool:
    issue_filters = workbench.get("issue_filters")
    if not isinstance(issue_filters, Mapping):
        return False
    filter_rows = issue_filters.get("filters")
    if not isinstance(filter_rows, list):
        return False
    seen = {str(row.get("filter_key")) for row in filter_rows if isinstance(row, Mapping)}
    return {"missing_date", "missing_actor", "contradictory_chronology", "procedural_significance"} <= seen


def _has_inspector_classification(workbench: Mapping[str, Any]) -> bool:
    classification = workbench.get("inspector_classification")
    if not isinstance(classification, Mapping):
        return False
    facts = classification.get("facts")
    if not isinstance(facts, Mapping) or not facts:
        return False
    return any(
        isinstance(row, Mapping)
        and isinstance(row.get("status_keys"), Mapping)
        and {"party_assertion", "procedural_outcome", "later_annotation"} <= set(row.get("status_keys", {}).keys())
        for row in facts.values()
    )


def _fact_rows(workbench: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    facts = workbench.get("facts")
    return [row for row in facts if isinstance(row, Mapping)] if isinstance(facts, list) else []


def _observation_rows(workbench: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    observations = workbench.get("observations")
    return [row for row in observations if isinstance(row, Mapping)] if isinstance(observations, list) else []


def _has_any_signal_class(workbench: Mapping[str, Any], *classes: str) -> bool:
    targets = set(classes)
    for row in _fact_rows(workbench):
        signal_set = set(row.get("signal_classes", [])) | set(row.get("source_signal_classes", []))
        if signal_set & targets:
            return True
    for row in _observation_rows(workbench):
        provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
        signal_set = set(provenance.get("signal_classes", []))
        if signal_set & targets:
            return True
    return False


def _has_abstention_visibility(workbench: Mapping[str, Any]) -> bool:
    facts = _fact_rows(workbench)
    if any(
        row.get("candidate_status") == "abstained" or "candidate_abstained" in set(row.get("reason_codes", []))
        for row in facts
    ):
        return True
    return any(str(row.get("observation_status") or "") == "abstained" for row in _observation_rows(workbench))


def _has_source_class_distinction(workbench: Mapping[str, Any]) -> bool:
    seen: set[str] = set()
    for row in _fact_rows(workbench):
        seen.update(str(value) for value in row.get("source_signal_classes", []) if str(value).strip())
    relevant = {"user_authored", "support_worker_note", "third_party_record", "later_annotation", "public_summary", "legal_record"}
    return len(seen & relevant) >= 2


def _has_support_handoff_posture(workbench: Mapping[str, Any]) -> bool:
    facts = _fact_rows(workbench)
    return any("support_worker_note" in set(row.get("source_signal_classes", [])) for row in facts) and any(
        {"user_authored", "party_material"} & set(row.get("source_signal_classes", [])) for row in facts
    )


def _has_source_local_wording_preserved(workbench: Mapping[str, Any]) -> bool:
    facts = _fact_rows(workbench)
    return any(
        bool(row.get("statement_ids"))
        and bool(row.get("source_ids"))
        and (
            {"public_summary", "wiki_article", "legal_record", "procedural_record", "reporting_source"}
            & set(row.get("source_signal_classes", []))
        )
        for row in facts
    )


def _has_public_knowledge_not_authority(workbench: Mapping[str, Any]) -> bool:
    seen: set[str] = set()
    for row in _fact_rows(workbench):
        seen.update(str(value) for value in row.get("source_signal_classes", []) if str(value).strip())
    return bool({"public_summary", "wiki_article", "weak_public_source"} & seen) and bool(
        {"legal_record", "procedural_record", "strong_legal_source"} & seen
    )


def _has_wiki_wikidata_claim_alignment(workbench: Mapping[str, Any]) -> bool:
    return any(
        "wikidata_claim" in set(row.get("source_signal_classes", []))
        and (
            {"identity_claim", "structural_ambiguity", "procedural_outcome"} & set(row.get("signal_classes", []))
            or {"wiki_article", "public_summary"} & set(row.get("source_signal_classes", []))
        )
        for row in _fact_rows(workbench)
    )


def _has_legal_circumstance_fidelity(workbench: Mapping[str, Any]) -> bool:
    return _has_source_local_wording_preserved(workbench) and _has_assertion_outcome_distinction(workbench) and _has_public_knowledge_not_authority(workbench)


def _has_argument_surface_not_proof(workbench: Mapping[str, Any]) -> bool:
    return _has_public_knowledge_not_authority(workbench) and _is_read_only_posture(workbench)


def _has_defamation_sensitive_posture(workbench: Mapping[str, Any]) -> bool:
    return _has_assertion_outcome_distinction(workbench) and _has_contested_summary(workbench) and _is_read_only_posture(workbench)


def _has_structural_boundary_visibility(workbench: Mapping[str, Any]) -> bool:
    return any(
        {"structural_ambiguity", "identity_claim", "office_holder_role", "institutional_boundary"} & set(row.get("signal_classes", []))
        or {"office_record", "institutional_record", "jurisdiction_record"} & set(row.get("source_signal_classes", []))
        for row in _fact_rows(workbench)
    )


def _has_adversarial_overstatement_visible(workbench: Mapping[str, Any]) -> bool:
    return _has_any_signal_class(workbench, "overstatement_risk", "public_summary_claim", "unsupported_assertion")


def _has_minimization_visible(workbench: Mapping[str, Any]) -> bool:
    return _has_any_signal_class(workbench, "minimization_risk")


def _has_source_shopping_visible(workbench: Mapping[str, Any]) -> bool:
    return _has_any_signal_class(workbench, "source_shopping_risk") and _has_public_knowledge_not_authority(workbench)


def _has_party_side_distinction(workbench: Mapping[str, Any]) -> bool:
    seen: set[str] = set()
    for row in _fact_rows(workbench):
        seen.update(str(value) for value in row.get("source_signal_classes", []) if str(value).strip())
    return bool({"side_a_material", "client_account"} & seen) and bool({"side_b_material", "other_side_account"} & seen)


def _has_child_sensitive_context(workbench: Mapping[str, Any]) -> bool:
    return _has_any_signal_class(workbench, "child_sensitive_context", "child_related_issue")


def _has_cross_side_handoff(workbench: Mapping[str, Any]) -> bool:
    return _has_party_side_distinction(workbench) and _has_workflow_link(workbench) and _has_source_class_distinction(workbench)


def _has_clinical_narrative_distinction(workbench: Mapping[str, Any]) -> bool:
    seen: set[str] = set()
    for row in _fact_rows(workbench):
        seen.update(str(value) for value in row.get("source_signal_classes", []) if str(value).strip())
    return bool({"clinical_record"} & seen) and bool({"patient_account"} & seen) and bool({"expert_interpretation"} & seen)


def _has_treatment_warning_harm_visibility(workbench: Mapping[str, Any]) -> bool:
    return _has_any_signal_class(workbench, "treatment_event", "warning_issue", "harm_consequence")


def _has_regulatory_stage_visibility(workbench: Mapping[str, Any]) -> bool:
    return _has_any_signal_class(workbench, "complaint_stage", "investigation_stage", "finding_stage", "sanction_stage")


def _has_public_narrative_vs_regulatory_record(workbench: Mapping[str, Any]) -> bool:
    seen: set[str] = set()
    for row in _fact_rows(workbench):
        seen.update(str(value) for value in row.get("source_signal_classes", []) if str(value).strip())
    return bool({"public_summary", "reporting_source"} & seen) and bool({"regulatory_record", "tribunal_record", "legal_record"} & seen)


def _has_professional_note_distinction(workbench: Mapping[str, Any]) -> bool:
    seen: set[str] = set()
    for row in _fact_rows(workbench):
        seen.update(str(value) for value in row.get("source_signal_classes", []) if str(value).strip())
    return bool({"user_authored", "client_account", "patient_account"} & seen) and bool(
        {"professional_note", "professional_interpretation"} & seen
    ) and bool({"third_party_record", "documentary_record", "legal_record"} & seen)


def _has_professional_handoff_posture(workbench: Mapping[str, Any]) -> bool:
    return _has_workflow_link(workbench) and _has_source_class_distinction(workbench) and _has_professional_note_distinction(workbench)


def _has_false_coherence_resistance(workbench: Mapping[str, Any]) -> bool:
    return _supports_sparse_chronology(workbench) and _has_abstention_visibility(workbench) and _has_any_signal_class(
        workbench,
        "fragmentary_account",
        "contradiction_cluster",
        "not_enough_evidence",
        "uncertainty_preserved",
    )


def _has_zelph_epistemic_validation(workbench: Mapping[str, Any]) -> bool:
    # This check specifically looks for the 'volatility_signal' stressors 
    # being surfaced through Zelph-like logic.
    # In the current implementation, we are looking for 'is_reversion' observations
    # and ensuring they are visible in the contested summary or signal classes.
    return _has_any_signal_class(workbench, "volatility_signal") and _has_contested_summary(workbench)


CheckFn = Callable[[Mapping[str, Any]], bool]

STORY_CHECKS: tuple[tuple[str, str, tuple[tuple[str, CheckFn], ...]], ...] = (
    (
        "SL-US-09",
        "Community legal centre intake triage",
        (
            ("provenance_drilldown", _has_provenance_links),
            ("review_queue", _has_review_queue),
            ("chronology_split", _has_chronology_split),
            ("roleful_queue_reasons", _has_roleful_queue_reasons),
            ("queue_grouping", _has_queue_grouping),
            ("inspector_classification", _has_inspector_classification),
        ),
    ),
    (
        "SL-US-10",
        "NGO litigation campaign case assembly",
        (
            ("provenance_drilldown", _has_provenance_links),
            ("contested_summary", _has_contested_summary),
            ("workflow_link", _has_workflow_link),
            ("reopen_navigation", _has_reopen_navigation),
        ),
    ),
    (
        "SL-US-11",
        "Paralegal evidence pack preparation",
        (
            ("provenance_drilldown", _has_provenance_links),
            ("review_queue", _has_review_queue),
            ("chronology_split", _has_chronology_split),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
        ),
    ),
    (
        "SL-US-12",
        "Solicitor case theory preparation",
        (
            ("provenance_drilldown", _has_provenance_links),
            ("contested_summary", _has_contested_summary),
            ("legal_procedural_signal", _has_legal_procedural_signal),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
        ),
    ),
    (
        "SL-US-13",
        "Barrister chronology and contradiction prep",
        (
            ("chronology_split", _has_chronology_split),
            ("contested_summary", _has_contested_summary),
            ("workflow_link", _has_workflow_link),
            ("approximate_chronology", _has_approximate_chronology),
        ),
    ),
    (
        "SL-US-14",
        "Judge / associate procedural reconstruction",
        (
            ("legal_procedural_signal", _has_legal_procedural_signal),
            ("read_only_posture", _is_read_only_posture),
            ("provenance_drilldown", _has_provenance_links),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
        ),
    ),
    (
        "ITIR-US-11",
        "Personal user memory reconstruction",
        (
            ("provenance_drilldown", _has_provenance_links),
            ("sparse_chronology", _supports_sparse_chronology),
            ("contested_summary", _has_contested_summary),
        ),
    ),
    (
        "ITIR-US-12",
        "General ITIR investigative user",
        (
            ("workflow_link", _has_workflow_link),
            ("review_queue", _has_review_queue),
            ("chronology_split", _has_chronology_split),
        ),
    ),
    (
        "ITIR-US-13",
        "Trauma-survivor safe reconstruction",
        (
            ("sparse_chronology", _supports_sparse_chronology),
            ("contested_summary", _has_contested_summary),
            ("read_only_posture", _is_read_only_posture),
            ("abstention_visibility", _has_abstention_visibility),
            ("source_class_distinction", _has_source_class_distinction),
        ),
    ),
    (
        "ITIR-US-14",
        "Support worker / advocate timeline assist",
        (
            ("provenance_drilldown", _has_provenance_links),
            ("roleful_queue_reasons", _has_roleful_queue_reasons),
            ("read_only_posture", _is_read_only_posture),
            ("source_class_distinction", _has_source_class_distinction),
            ("support_handoff_posture", _has_support_handoff_posture),
        ),
    ),
    (
        "SL-US-15",
        "Wikipedia moderator on highly contested public-figure pages",
        (
            ("source_local_wording_preserved", _has_source_local_wording_preserved),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
            ("defamation_sensitive_posture", _has_defamation_sensitive_posture),
            ("public_knowledge_not_authority", _has_public_knowledge_not_authority),
            ("zelph_epistemic_validation", _has_zelph_epistemic_validation),
        ),
    ),
    (
        "SL-US-16",
        "Wikidata ontology / claim worker on contested entities",
        (
            ("wiki_wikidata_claim_alignment", _has_wiki_wikidata_claim_alignment),
            ("structural_boundary_visibility", _has_structural_boundary_visibility),
            ("contested_summary", _has_contested_summary),
            ("public_knowledge_not_authority", _has_public_knowledge_not_authority),
        ),
    ),
    (
        "SL-US-17",
        "Mereology / structure worker for institutional or composite actors",
        (
            ("structural_boundary_visibility", _has_structural_boundary_visibility),
            ("provenance_drilldown", _has_provenance_links),
        ),
    ),
    (
        "SL-US-18",
        "Lawyer assessing legality of public-figure conduct",
        (
            ("legal_circumstance_fidelity", _has_legal_circumstance_fidelity),
            ("legal_procedural_signal", _has_legal_procedural_signal),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
            ("public_knowledge_not_authority", _has_public_knowledge_not_authority),
        ),
    ),
    (
        "SL-US-19",
        "Wikipedia legal-circumstance fidelity review",
        (
            ("legal_circumstance_fidelity", _has_legal_circumstance_fidelity),
            ("source_local_wording_preserved", _has_source_local_wording_preserved),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
        ),
    ),
    (
        "SL-US-20",
        "Lawyer using Wikipedia as a starting argument surface",
        (
            ("argument_surface_not_proof", _has_argument_surface_not_proof),
            ("source_local_wording_preserved", _has_source_local_wording_preserved),
            ("public_knowledge_not_authority", _has_public_knowledge_not_authority),
        ),
    ),
    (
        "SL-US-21",
        "Lawyer-maintainer conflict over wiki-based legal framing",
        (
            ("source_local_wording_preserved", _has_source_local_wording_preserved),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
            ("contested_summary", _has_contested_summary),
            ("defamation_sensitive_posture", _has_defamation_sensitive_posture),
        ),
    ),
    (
        "SL-US-22",
        "Adversarial overstatement of legal record",
        (
            ("adversarial_overstatement_visible", _has_adversarial_overstatement_visible),
            ("source_local_wording_preserved", _has_source_local_wording_preserved),
        ),
    ),
    (
        "SL-US-23",
        "Adversarial minimization or sanitization",
        (
            ("minimization_visible", _has_minimization_visible),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
        ),
    ),
    (
        "SL-US-24",
        "Source-shopping and narrative cherry-picking",
        (
            ("source_shopping_visible", _has_source_shopping_visible),
            ("public_knowledge_not_authority", _has_public_knowledge_not_authority),
        ),
    ),
    (
        "SL-US-25",
        "Family-law client circumstance reconstruction",
        (
            ("party_side_distinction", _has_party_side_distinction),
            ("chronology_split", _has_chronology_split),
            ("contested_summary", _has_contested_summary),
            ("child_sensitive_context", _has_child_sensitive_context),
        ),
    ),
    (
        "SL-US-26",
        "Family-law lawyer preparing both-sides circumstance review",
        (
            ("party_side_distinction", _has_party_side_distinction),
            ("legal_procedural_signal", _has_legal_procedural_signal),
            ("child_sensitive_context", _has_child_sensitive_context),
            ("provenance_drilldown", _has_provenance_links),
        ),
    ),
    (
        "SL-US-27",
        "Child-sensitive circumstance review",
        (
            ("child_sensitive_context", _has_child_sensitive_context),
            ("sparse_chronology", _supports_sparse_chronology),
            ("assertion_outcome_distinction", _has_assertion_outcome_distinction),
        ),
    ),
    (
        "SL-US-28",
        "Provenance-preserving cross-side handoff",
        (
            ("cross_side_handoff", _has_cross_side_handoff),
            ("workflow_link", _has_workflow_link),
            ("source_class_distinction", _has_source_class_distinction),
            ("provenance_drilldown", _has_provenance_links),
        ),
    ),
    (
        "SL-US-29",
        "Medical negligence circumstance review",
        (
            ("treatment_warning_harm_visibility", _has_treatment_warning_harm_visibility),
            ("clinical_narrative_distinction", _has_clinical_narrative_distinction),
            ("chronology_split", _has_chronology_split),
        ),
    ),
    (
        "SL-US-30",
        "Professional discipline / regulatory record review",
        (
            ("regulatory_stage_visibility", _has_regulatory_stage_visibility),
            ("structural_boundary_visibility", _has_structural_boundary_visibility),
            ("public_narrative_vs_regulatory_record", _has_public_narrative_vs_regulatory_record),
        ),
    ),
    (
        "ITIR-US-15",
        "Personal-to-professional provenance handoff",
        (
            ("workflow_link", _has_workflow_link),
            ("provenance_drilldown", _has_provenance_links),
            ("professional_handoff_posture", _has_professional_handoff_posture),
            ("source_class_distinction", _has_source_class_distinction),
            ("abstention_visibility", _has_abstention_visibility),
        ),
    ),
    (
        "ITIR-US-16",
        "Combating AI psychosis / false-coherence escalation",
        (
            ("false_coherence_resistance", _has_false_coherence_resistance),
            ("provenance_drilldown", _has_provenance_links),
            ("read_only_posture", _is_read_only_posture),
            ("abstention_visibility", _has_abstention_visibility),
            ("contested_summary", _has_contested_summary),
        ),
    ),
)

STORY_WAVES: dict[str, tuple[str, ...]] = {
    "wave1_legal": ("SL-US-09", "SL-US-10", "SL-US-11", "SL-US-12", "SL-US-13", "SL-US-14"),
    "wave2_balanced": ("ITIR-US-11", "ITIR-US-12"),
    "wave3_trauma_advocacy": ("ITIR-US-13", "ITIR-US-14"),
    "wave3_public_knowledge": ("SL-US-15", "SL-US-16", "SL-US-17", "SL-US-18", "SL-US-19", "SL-US-20", "SL-US-21", "SL-US-22", "SL-US-23", "SL-US-24"),
    "wave4_family_law": ("SL-US-25", "SL-US-26", "SL-US-27", "SL-US-28"),
    "wave4_medical_regulatory": ("SL-US-29", "SL-US-30"),
    "wave5_handoff_false_coherence": ("ITIR-US-15", "ITIR-US-16"),
    "all": tuple(story_id for story_id, _label, _checks in STORY_CHECKS),
}

CHECK_EXPLANATIONS: dict[str, str] = {
    "provenance_drilldown": "Missing drill-down from fact/event rows to source statements and excerpts.",
    "review_queue": "Missing actionable review queue for follow-up work.",
    "chronology_split": "Chronology is not clearly separated into dated, undated, and no-event material.",
    "roleful_queue_reasons": "Review queue reasons are still too generic for operator triage.",
    "queue_grouping": "Review queue lacks grouped/filterable issue categories.",
    "contested_summary": "Contested items are not summarized separately from the main review flow.",
    "workflow_link": "Stored run cannot be reopened cleanly from workflow metadata.",
    "reopen_navigation": "Source-centric reopen navigation is not explicit enough in the persisted workbench.",
    "legal_procedural_signal": "Legal/procedural observations are not visible enough in the review surface.",
    "assertion_outcome_distinction": "Party assertion, later annotation, and procedural outcome are still blurred together.",
    "inspector_classification": "Inspector does not explicitly distinguish assertion, procedural outcome, and later annotation.",
    "read_only_posture": "Review surface does not clearly maintain read-only, non-reasoning posture.",
    "sparse_chronology": "Sparse chronology handling is too weak for contradictory or partial material.",
    "approximate_chronology": "Approximate or relative dates are not surfaced distinctly enough.",
    "abstention_visibility": "Abstained or not-ready material is not visible enough in the review surface.",
    "source_class_distinction": "User-authored, support-note, and third-party source classes are not distinguishable enough.",
    "support_handoff_posture": "Support-worker handoff posture is not visible enough in the shared review surface.",
    "source_local_wording_preserved": "Source-local wording is not visible enough beside the derived review surface.",
    "defamation_sensitive_posture": "Moderation-sensitive or defamation-risk posture is not explicit enough.",
    "public_knowledge_not_authority": "Public-summary or wiki-shaped material is not kept distinct enough from stronger legal authority.",
    "wiki_wikidata_claim_alignment": "Wiki/Wikidata claim pressure and alignment are not visible enough.",
    "legal_circumstance_fidelity": "Public wording is not being checked against legal-stage and procedural material clearly enough.",
    "argument_surface_not_proof": "Wikipedia/public-summary material is not framed clearly enough as navigational rather than authoritative.",
    "structural_boundary_visibility": "Person, office, institution, and jurisdiction boundaries are not visible enough.",
    "adversarial_overstatement_visible": "Overstatement pressure is not explicit enough in the review surface.",
    "minimization_visible": "Minimization or sanitization pressure is not explicit enough in the review surface.",
    "source_shopping_visible": "Source-shopping or narrative cherry-picking pressure is not explicit enough.",
    "party_side_distinction": "Side A, side B, and client-side material are not distinguishable enough.",
    "child_sensitive_context": "Child-sensitive context is not explicit enough in the review surface.",
    "cross_side_handoff": "Cross-side or cross-recipient handoff posture is not preserved clearly enough.",
    "clinical_narrative_distinction": "Clinical record, patient account, and later interpretation are not distinguishable enough.",
    "treatment_warning_harm_visibility": "Treatment, warning, and harm visibility is too weak for medical review.",
    "regulatory_stage_visibility": "Complaint, investigation, finding, and sanction stages are not visible enough.",
    "public_narrative_vs_regulatory_record": "Public narrative and regulatory/legal record are not separable enough.",
    "professional_handoff_posture": "Personal, documentary, and later professional layers are not distinguishable enough across handoff.",
    "false_coherence_resistance": "High-conflict sparse material is still too easy to collapse into one narrative.",
    "zelph_epistemic_validation": "Missing epistemic volatility signals (reversions, archival shifts) expected from real wiki history.",
}

CHECK_GAP_TAGS: dict[str, tuple[str, ...]] = {
    "roleful_queue_reasons": ("review_queue_generic",),
    "queue_grouping": ("workbench_filter_missing", "review_queue_generic"),
    "legal_procedural_signal": ("procedural_signal_thin",),
    "assertion_outcome_distinction": ("assertion_outcome_blur",),
    "inspector_classification": ("assertion_outcome_blur",),
    "approximate_chronology": ("chronology_sparse_dates",),
    "sparse_chronology": ("chronology_sparse_dates", "anti_false_coherence_risk"),
    "workflow_link": ("reopen_navigation_gap",),
    "reopen_navigation": ("reopen_navigation_gap",),
    "abstention_visibility": ("anti_false_coherence_risk", "uncertainty_visibility_gap"),
    "source_class_distinction": ("handoff_context_gap",),
    "support_handoff_posture": ("handoff_context_gap",),
    "source_local_wording_preserved": ("source_wording_hidden",),
    "defamation_sensitive_posture": ("defamation_posture_gap",),
    "public_knowledge_not_authority": ("authority_transfer_risk",),
    "wiki_wikidata_claim_alignment": ("claim_alignment_gap",),
    "legal_circumstance_fidelity": ("legal_record_fidelity_gap",),
    "argument_surface_not_proof": ("authority_transfer_risk",),
    "structural_boundary_visibility": ("mereology_boundary_gap",),
    "adversarial_overstatement_visible": ("overstatement_risk_hidden",),
    "minimization_visible": ("sanitization_risk_hidden",),
    "source_shopping_visible": ("source_shopping_hidden",),
    "party_side_distinction": ("cross_side_boundary_gap",),
    "child_sensitive_context": ("child_context_gap",),
    "cross_side_handoff": ("handoff_context_gap", "cross_side_boundary_gap"),
    "clinical_narrative_distinction": ("clinical_narrative_blur",),
    "treatment_warning_harm_visibility": ("medical_visibility_gap",),
    "regulatory_stage_visibility": ("regulatory_stage_gap",),
    "public_narrative_vs_regulatory_record": ("authority_transfer_risk", "regulatory_record_gap"),
    "professional_handoff_posture": ("handoff_context_gap", "professional_layer_blur"),
    "false_coherence_resistance": ("anti_false_coherence_risk", "uncertainty_visibility_gap"),
}


def build_fact_review_acceptance_report(
    workbench: Mapping[str, Any],
    *,
    fixture_kind: str = "unknown",
    wave: str = "all",
    story_ids: list[str] | None = None,
) -> dict[str, Any]:
    target_story_ids = set(story_ids or STORY_WAVES.get(wave, STORY_WAVES["all"]))
    story_results: list[dict[str, Any]] = []
    passed = 0
    partial = 0
    failed = 0
    for story_id, label, checks in STORY_CHECKS:
        if story_id not in target_story_ids:
            continue
        check_rows = [
            {
                "check_id": check_id,
                "passed": bool(check_fn(workbench)),
                "explanation": CHECK_EXPLANATIONS.get(check_id),
            }
            for check_id, check_fn in checks
        ]
        passed_count = sum(1 for row in check_rows if row["passed"])
        failed_checks = [row["check_id"] for row in check_rows if not row["passed"]]
        gap_tags = sorted(
            {
                gap_tag
                for check_id in failed_checks
                for gap_tag in CHECK_GAP_TAGS.get(check_id, ())
            }
        )
        if passed_count == len(check_rows):
            status = "pass"
            passed += 1
        elif passed_count == 0:
            status = "fail"
            failed += 1
        else:
            status = "partial"
            partial += 1
        story_results.append(
            {
                "story_id": story_id,
                "label": label,
                "status": status,
                "check_count": len(check_rows),
                "passed_check_count": passed_count,
                "failed_check_ids": failed_checks,
                "gap_tags": gap_tags,
                "blocking_explanation": " ".join(
                    CHECK_EXPLANATIONS[check_id]
                    for check_id in failed_checks
                    if check_id in CHECK_EXPLANATIONS
                ) or None,
                "checks": check_rows,
            }
        )
    run = workbench.get("run") if isinstance(workbench.get("run"), Mapping) else {}
    return {
        "version": FACT_REVIEW_ACCEPTANCE_VERSION,
        "wave": wave,
        "fixture_kind": fixture_kind,
        "run": {
            "run_id": run.get("run_id"),
            "source_label": run.get("source_label"),
            "workflow_link": run.get("workflow_link"),
        },
        "summary": {
            "story_count": len(story_results),
            "pass_count": passed,
            "partial_count": partial,
            "fail_count": failed,
        },
        "stories": story_results,
    }


def build_fact_review_acceptance_batch_report(
    fixture_reports: list[Mapping[str, Any]],
    *,
    wave: str,
) -> dict[str, Any]:
    fixture_rows: list[dict[str, Any]] = []
    story_rollup: dict[str, dict[str, Any]] = {}
    gap_rollup: dict[str, dict[str, Any]] = {}
    for row in fixture_reports:
        acceptance = row.get("acceptance") if isinstance(row, Mapping) else None
        fixture = row.get("fixture") if isinstance(row, Mapping) else None
        if not isinstance(acceptance, Mapping) or not isinstance(fixture, Mapping):
            continue
        fixture_rows.append(
            {
                "fixture_id": fixture.get("fixture_id"),
                "fixture_kind": fixture.get("fixture_kind"),
                "fixture_family": fixture.get("fixture_family"),
                "risk_class": fixture.get("risk_class"),
                "workflow_kind": fixture.get("workflow_kind"),
                "source_label": fixture.get("source_label"),
                "target_story_ids": list(fixture.get("target_story_ids") or []),
                "stressors": list(fixture.get("stressors") or []),
                "run": acceptance.get("run"),
                "summary": acceptance.get("summary"),
                "stories": acceptance.get("stories"),
            }
        )
        for story in acceptance.get("stories", []):
            if not isinstance(story, Mapping):
                continue
            story_entry = story_rollup.setdefault(
                str(story.get("story_id")),
                {
                    "story_id": story.get("story_id"),
                    "label": story.get("label"),
                    "fixture_results": [],
                    "pass_count": 0,
                    "partial_count": 0,
                    "fail_count": 0,
                },
            )
            story_entry["fixture_results"].append(
                {
                    "fixture_id": fixture.get("fixture_id"),
                    "status": story.get("status"),
                    "failed_check_ids": list(story.get("failed_check_ids") or []),
                    "gap_tags": list(story.get("gap_tags") or []),
                }
            )
            story_entry[f"{story.get('status')}_count"] += 1
            for gap_tag in story.get("gap_tags", []):
                gap_entry = gap_rollup.setdefault(
                    str(gap_tag),
                    {"gap_tag": gap_tag, "count": 0, "fixtures": set(), "stories": set()},
                )
                gap_entry["count"] += 1
                gap_entry["fixtures"].add(str(fixture.get("fixture_id")))
                gap_entry["stories"].add(str(story.get("story_id")))
    ordered_story_rollup = sorted(
        (
            {
                **entry,
                "fixture_results": sorted(entry["fixture_results"], key=lambda row: (row["status"], row["fixture_id"])),
            }
            for entry in story_rollup.values()
        ),
        key=lambda row: row["story_id"],
    )
    ordered_gap_rollup = sorted(
        (
            {
                "gap_tag": entry["gap_tag"],
                "count": entry["count"],
                "fixtures": sorted(entry["fixtures"]),
                "stories": sorted(entry["stories"]),
            }
            for entry in gap_rollup.values()
        ),
        key=lambda row: (-row["count"], row["gap_tag"]),
    )
    return {
        "version": FACT_REVIEW_ACCEPTANCE_BATCH_VERSION,
        "wave": wave,
        "fixture_count": len(fixture_rows),
        "fixtures": fixture_rows,
        "stories": ordered_story_rollup,
        "gaps": ordered_gap_rollup,
    }
