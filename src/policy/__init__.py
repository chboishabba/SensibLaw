import os
import sys

from .semantic_promotion import (
    ABSTAINED,
    CANDIDATE_BASES,
    CANDIDATE_CONFLICT,
    CONTESTED_CANDIDATE_SCHEMA_VERSION,
    HOTSPOT_PACK_CANDIDATE_SCHEMA_VERSION,
    MANDATORY_CONTESTED_CANDIDATE_FIELDS,
    MANDATORY_HOTSPOT_PACK_CANDIDATE_FIELDS,
    MANDATORY_RELATION_CANDIDATE_FIELDS,
    NON_TRUTH_BEARING_FIELDS,
    PROMOTED_FALSE,
    PROMOTED_TRUE,
    PROMOTION_STATUSES,
    RELATION_CANDIDATE_SCHEMA_VERSION,
    SEMANTIC_PROMOTION_VERSION,
    TRUTH_BEARING_FIELDS,
    build_contested_claim_candidate,
    build_hotspot_pack_candidate,
    build_relation_candidate,
    derive_relation_semantic_basis,
    promote_contested_claim,
    promote_hotspot_pack_candidate,
    promote_relation_candidate,
    validate_contested_claim_candidate,
    validate_hotspot_pack_candidate,
    validate_relation_candidate,
)
from .proposition_contradiction_taxonomy import (
    PROPOSITION_CONTRADICTION_LABELS,
    PROPOSITION_CONTRADICTION_TAXONOMY_VERSION,
    build_proposition_contradiction_taxonomy,
    validate_proposition_contradiction_label,
)
from .proposition_resolution_policy import (
    PROPOSITION_RESOLUTION_POLICY_VERSION,
    PROPOSITION_RESOLUTION_STATES,
    build_proposition_resolution_policy,
    validate_proposition_resolution_state,
)
from .control_profiles import (
    CONTROL_PROFILE_SCHEMA_VERSION,
    ISO_TRACEABILITY_MIN_PROFILE,
    get_control_profile,
    list_control_profiles,
    normalize_control_profile,
)
from .control_evidence import (
    COMPLIANCE_EVIDENCE_BUNDLE_SCHEMA_VERSION,
    SB_TO_SL_ALLOWED_FIELDS,
    SB_TO_SL_CONSUMER_CONTRACT_VERSION,
    SB_TO_SL_FORBIDDEN_FIELDS,
    build_compliance_evidence_bundle,
    build_sb_to_sl_contract_payload,
    validate_sb_to_sl_contract_payload,
)
from .control_evaluator import (
    CONTROL_ASSESSMENT_SCHEMA_VERSION,
    CONTROL_ASSESSMENT_STATUSES,
    evaluate_clause,
    evaluate_control_group,
    evaluate_control_profile,
)
from .compliance_assessment import (
    COMPLIANCE_ASSESSMENT_SCHEMA_VERSION,
    build_compliance_assessment,
)
from .sl_to_sb_observer import (
    SL_TO_SB_ISO_RUN_OBSERVER_CONTRACT_VERSION,
    SL_TO_SB_ISO_RUN_OBSERVER_KIND,
    build_sl_to_sb_iso_run_observer_payload,
)


def _bounded_execution_enabled() -> bool:
    value = os.environ.get("SENSIBLAW_BOUNDED_DOCUMENT_EXECUTION", "1")
    return value.strip().lower() not in {"0", "false", "no", "off"}


_execution_strategies_installed = False
_execution_strategies_installing = False


def install_execution_strategies() -> None:
    """Install execution policy after the neutral PNF package is available."""

    global _execution_strategies_installed, _execution_strategies_installing
    if (
        _execution_strategies_installed
        or _execution_strategies_installing
        or not _bounded_execution_enabled()
    ):
        return
    _execution_strategies_installing = True
    # Execution-strategy installation only: corpus_compilation and
    # operational_corpus_compilation remain the sole semantic authorities.
    try:
        from .bounded_operational_execution import (
            install_bounded_operational_execution,
        )
        from .closure_finalization_hardening import (
            install_closure_finalization_hardening,
        )
        from .closure_hot_path_execution import install_closure_hot_path_execution
        from .closure_liveness_execution import (
            install_closure_liveness_execution,
        )
        from .dependency_indexed_owner_execution import (
            install_dependency_indexed_owner_execution,
        )
        from .indexed_projection_execution import (
            indexed_projection_enabled,
            install_indexed_projection_execution,
        )
        from .owner_handoff_batch_performance import (
            install_owner_handoff_batch_performance,
        )
        from .owner_handoff_performance import (
            install_owner_handoff_performance,
        )
        from .parallel_semantic_execution import (
            install_parallel_semantic_execution,
        )
        from .parallel_typing_tail import install_parallel_typing_tail
        from .progress_observability_execution import (
            install_progress_observability_execution,
        )
        from .reduction_hot_path_execution import install_reduction_hot_path_execution
        from .reference_backed_finalization import (
            install_reference_backed_finalization,
        )
        from .scheduler_hot_path_execution import install_scheduler_hot_path_execution
        from .semantic_receipt_enrichment import (
            install_semantic_receipt_enrichment,
        )
        from .sparse_root_publication_execution import (
            install_sparse_root_publication_execution,
        )
        from .stage_budget_execution import install_stage_budget_execution

        if indexed_projection_enabled():
            install_indexed_projection_execution()
        install_bounded_operational_execution()
        # The bounded owner owns exact input availability. Index declared factor
        # and observation dependencies once and wake only reverse-dependency
        # successor owners until their local reduction fixed point is reached.
        install_dependency_indexed_owner_execution()
        # The sparse hierarchy publishes the canonical root once. Paragraph
        # adjacency remains residual/evidence-only under the current contract,
        # so the later root-global refresh is a certified no-op.
        install_sparse_root_publication_execution()
        # Harden the existing bounded owner before wrappers capture it: global
        # materialisation is deferred across admission batches and exhausted
        # frontiers terminate with a certificate or a finite diagnostic.
        install_closure_liveness_execution()
        # Keep diagnostics observational, stream the large terminal checkpoint,
        # and reuse matching reduction/certificate checkpoints after replay.
        install_closure_finalization_hardening()
        # Seal large families, release the owner state, then serialize only a
        # compact reference receipt in a fresh interpreter.
        install_reference_backed_finalization()
        # This wraps the already-installed bounded closure surface, adds
        # output-sensitive local-typing overlap leaves and closure receipt
        # replay, and leaves the canonical compiler as the sole authority.
        install_parallel_semantic_execution()
        # Replace cumulative tuple copies/full-history handoff snapshots with an
        # append-only replay journal plus compact frontier checkpoint, and cache
        # immutable content-addressed identities used by the hot admission path.
        install_owner_handoff_performance()
        # The bounded caller already filters activation rows against the
        # canonical owner's admitted-delta map. Do not rebuild/serialize a second
        # cumulative recorded-delta index inside the replay contract.
        install_owner_handoff_batch_performance()
        # The remaining hypothesis/type/diagnostic tails and pure closure
        # handlers are CPU-bound. Install process-backed bounded leaves after
        # telemetry so their outputs retain the same resource receipts.
        install_parallel_typing_tail()
        # Replace the reducer's linear scan over prior compatibility groups with
        # an exact first-match bitset lookup before the bounded hot path starts.
        install_reduction_hot_path_execution()
        # Keep the scheduler's canonical order key, but maintain its ready
        # frontier incrementally rather than repeatedly sorting the whole deque.
        install_scheduler_hot_path_execution()
        # The bounded executor captured its closure function before the process
        # wrapper existed. Rebind that hot path, select a CPU-aware default width,
        # and coalesce dependency-free full-fibre reductions while immutable
        # closure jobs remain in flight.
        install_closure_hot_path_execution()
        # Parent stages must expose child completion while leaves are running,
        # name waits, and persist the same universal envelope emitted to logs.
        install_progress_observability_execution()
        # Every semantic sample now also enforces a lower stage-local budget;
        # the global process limit remains the final safety net.
        install_stage_budget_execution()
        # The semantic wrapper writes its receipt in ``finally``. Enrichment is
        # intentionally installed last so completed artifact stage identities
        # can be copied into that durable receipt without changing output.
        install_semantic_receipt_enrichment()
        _execution_strategies_installed = True
    finally:
        _execution_strategies_installing = False


# PNF imports generic policy carriers. Installing strategies while that
# package is still importing re-enters its binding modules; PNF calls the
# explicit installer once its neutral exports are complete.
if (
    "src.pnf.binding_candidate_sets" not in sys.modules
    and "src.runtime.durable_work_items" not in sys.modules
):
    install_execution_strategies()


__all__ = [
    "ABSTAINED",
    "CANDIDATE_BASES",
    "CANDIDATE_CONFLICT",
    "COMPLIANCE_ASSESSMENT_SCHEMA_VERSION",
    "COMPLIANCE_EVIDENCE_BUNDLE_SCHEMA_VERSION",
    "CONTROL_ASSESSMENT_SCHEMA_VERSION",
    "CONTROL_ASSESSMENT_STATUSES",
    "CONTROL_PROFILE_SCHEMA_VERSION",
    "derive_relation_semantic_basis",
    "CONTESTED_CANDIDATE_SCHEMA_VERSION",
    "HOTSPOT_PACK_CANDIDATE_SCHEMA_VERSION",
    "ISO_TRACEABILITY_MIN_PROFILE",
    "RELATION_CANDIDATE_SCHEMA_VERSION",
    "MANDATORY_CONTESTED_CANDIDATE_FIELDS",
    "MANDATORY_HOTSPOT_PACK_CANDIDATE_FIELDS",
    "MANDATORY_RELATION_CANDIDATE_FIELDS",
    "NON_TRUTH_BEARING_FIELDS",
    "PROMOTED_FALSE",
    "PROMOTED_TRUE",
    "PROMOTION_STATUSES",
    "PROPOSITION_CONTRADICTION_LABELS",
    "PROPOSITION_CONTRADICTION_TAXONOMY_VERSION",
    "PROPOSITION_RESOLUTION_POLICY_VERSION",
    "PROPOSITION_RESOLUTION_STATES",
    "SB_TO_SL_ALLOWED_FIELDS",
    "SB_TO_SL_CONSUMER_CONTRACT_VERSION",
    "SB_TO_SL_FORBIDDEN_FIELDS",
    "SEMANTIC_PROMOTION_VERSION",
    "SL_TO_SB_ISO_RUN_OBSERVER_CONTRACT_VERSION",
    "SL_TO_SB_ISO_RUN_OBSERVER_KIND",
    "TRUTH_BEARING_FIELDS",
    "build_compliance_assessment",
    "build_compliance_evidence_bundle",
    "build_proposition_contradiction_taxonomy",
    "build_proposition_resolution_policy",
    "build_contested_claim_candidate",
    "build_hotspot_pack_candidate",
    "build_relation_candidate",
    "build_sb_to_sl_contract_payload",
    "build_sl_to_sb_iso_run_observer_payload",
    "evaluate_clause",
    "evaluate_control_group",
    "evaluate_control_profile",
    "get_control_profile",
    "list_control_profiles",
    "normalize_control_profile",
    "promote_contested_claim",
    "promote_hotspot_pack_candidate",
    "promote_relation_candidate",
    "validate_sb_to_sl_contract_payload",
    "validate_proposition_contradiction_label",
    "validate_proposition_resolution_state",
    "validate_contested_claim_candidate",
    "validate_hotspot_pack_candidate",
    "validate_relation_candidate",
]
