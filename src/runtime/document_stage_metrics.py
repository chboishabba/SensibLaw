"""Named throughput measures for document compilation stages.

The registry is descriptive only. Compiler loops remain authoritative for the
observed counters and must update them while work is in progress.
"""

from __future__ import annotations

from typing import Any, Mapping


DOCUMENT_STAGE_MEASURES: dict[str, tuple[tuple[str, str], ...]] = {
    "canonical_normalization": (
        ("input_chars", "chars"),
        ("output_chars", "chars"),
        ("input_bytes", "bytes"),
        ("output_bytes", "bytes"),
    ),
    "parser_annotation": (
        ("chars", "chars"),
        ("fibres", "fibres"),
        ("sentences", "sentences"),
        ("tokens", "tokens"),
        ("dependencies", "dependencies"),
    ),
    "coordinate_validation": (
        ("tokens_checked", "tokens"),
        ("spans_checked", "spans"),
        ("coordinates_rejected", "coordinates"),
    ),
    "mention_licensing": (
        ("tokens_scanned", "tokens"),
        ("mentions_considered", "mentions"),
        ("mentions_licensed", "mentions"),
        ("recurrences_derived", "recurrences"),
        ("forms_derived", "forms"),
    ),
    "parser_observation_projection": (
        ("parser_tokens_projected", "tokens"),
        ("sentences_projected", "sentences"),
        ("observations_emitted", "observations"),
        ("deltas_emitted", "deltas"),
        ("relations_projected", "relations"),
        ("semantic_atoms_projected", "atoms"),
        ("semantic_relations_projected", "relations"),
        ("token_coverage_lookups", "lookups"),
        ("lookup_operations", "lookups"),
        ("bundle_batches_completed", "batches"),
        ("bundle_sentences_scanned", "sentences"),
        ("bundle_words_scanned", "words"),
        ("bundle_tokens_scanned", "tokens"),
        ("batch_elapsed_ms", "milliseconds"),
        ("last_batch_size", "atoms"),
        ("rss_bytes", "bytes"),
        ("process_tree_rss_bytes", "bytes"),
        ("gc_collection_counts", "collections"),
        ("retained_object_counts", "objects"),
    ),
    "local_typing_diagnostics": (
        ("mentions_considered", "mentions"),
        ("typing_hypotheses_derived", "hypotheses"),
        ("diagnostics_evaluated", "diagnostics"),
    ),
    "base_proposal_generation": (
        ("atoms_scanned", "atoms"),
        ("relations_scanned", "relations"),
        ("proposals_generated", "proposals"),
        ("factors_emitted", "factors"),
        ("constraints_emitted", "constraints"),
    ),
    "streaming_closure": (
        ("deltas_admitted", "deltas"),
        ("closure_jobs_ready", "jobs"),
        ("closure_jobs_leased", "jobs"),
        ("jobs_completed", "jobs"),
        ("input_refs_processed", "input_refs"),
        ("proposals_emitted", "proposals"),
        ("dirty_groups_reduced", "groups"),
        ("duplicates_collapsed", "proposals"),
        ("residuals_emitted", "residuals"),
        ("pending_jobs", "jobs"),
        ("in_flight_jobs", "jobs"),
        ("dirty_groups", "groups"),
        ("rss_bytes", "bytes"),
        ("process_tree_rss_bytes", "bytes"),
        ("retained_jobs", "jobs"),
        ("retained_receipts", "receipts"),
        ("retained_observation_deltas", "deltas"),
        ("deferred_jobs", "jobs"),
        ("pressure_events", "events"),
    ),
    "pnf_graph_construction": (
        ("factors_materialized", "factors"),
        ("constraints_materialized", "constraints"),
        ("relations_materialized", "relations"),
        ("residuals_materialized", "residuals"),
    ),
    "constraint_assessment": (
        ("factors_scanned", "factors"),
        ("constraints_evaluated", "constraints"),
        ("assessments_emitted", "assessments"),
        ("satisfied", "assessments"),
        ("violated", "assessments"),
        ("undetermined", "assessments"),
        ("inapplicable", "assessments"),
    ),
    "constraint_fixed_point": (
        ("factors_scanned", "factors"),
        ("constraints_evaluated", "constraints"),
        ("assessments_emitted", "assessments"),
        ("satisfied", "assessments"),
        ("violated", "assessments"),
        ("undetermined", "assessments"),
        ("inapplicable", "assessments"),
    ),
    "meet_refinement": (
        ("candidate_meets_considered", "candidates"),
        ("typed_meets_accepted", "meets"),
        ("refinements_proposed", "refinements"),
        ("refinements_applied", "refinements"),
        ("refinements_deduplicated", "refinements"),
        ("refinements_rejected", "refinements"),
        ("factors_rewritten", "factors"),
        ("residual_transitions", "transitions"),
        ("semantic_yield", "semantic_changes"),
    ),
    "demand_derivation": (
        ("factors_scanned", "factors"),
        ("demands_emitted", "demands"),
        ("demands_resolved", "demands"),
        ("demands_unresolved", "demands"),
    ),
    "binding_candidate_compaction": (
        ("candidates_before", "candidates"),
        ("candidates_after", "candidates"),
        ("candidates_removed", "candidates"),
        ("candidate_sets", "sets"),
    ),
    "postgres_persistence": (
        ("rows_written", "rows"),
        ("bytes_written", "bytes"),
        ("tables_touched", "tables"),
        ("statements_executed", "statements"),
        ("conflicts_avoided", "rows"),
    ),
}


def stage_measure_declaration(
    stage: str,
    *,
    totals: Mapping[str, int | float | None] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the initial measure vector for one declared stage."""

    totals = dict(totals or {})
    try:
        definitions = DOCUMENT_STAGE_MEASURES[stage]
    except KeyError as error:
        raise ValueError(f"undeclared document progress stage: {stage}") from error
    return {
        name: {
            "completed": 0,
            "unit": unit,
            **({"total": totals[name]} if totals.get(name) is not None else {}),
        }
        for name, unit in definitions
    }


__all__ = ["DOCUMENT_STAGE_MEASURES", "stage_measure_declaration"]
