from __future__ import annotations

import importlib
import sys

from .semantic_promotion import (
    ABSTAINED,
    CANDIDATE_BASES,
    CANDIDATE_CONFLICT,
    derive_relation_semantic_basis,
    CONTESTED_CANDIDATE_SCHEMA_VERSION,
    HOTSPOT_PACK_CANDIDATE_SCHEMA_VERSION,
    RELATION_CANDIDATE_SCHEMA_VERSION,
    MANDATORY_CONTESTED_CANDIDATE_FIELDS,
    MANDATORY_HOTSPOT_PACK_CANDIDATE_FIELDS,
    MANDATORY_RELATION_CANDIDATE_FIELDS,
    NON_TRUTH_BEARING_FIELDS,
    PROMOTED_FALSE,
    PROMOTED_TRUE,
    PROMOTION_STATUSES,
    SEMANTIC_PROMOTION_VERSION,
    TRUTH_BEARING_FIELDS,
    build_contested_claim_candidate,
    build_hotspot_pack_candidate,
    build_relation_candidate,
    promote_contested_claim,
    promote_hotspot_pack_candidate,
    promote_relation_candidate,
    validate_contested_claim_candidate,
    validate_hotspot_pack_candidate,
    validate_relation_candidate,
)
from .proposition_contradiction_taxonomy import (
    PROPOSITION_CONTRADICTION_TAXONOMY_VERSION,
    PROPOSITION_CONTRADICTION_LABELS,
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
    SB_TO_SL_CONSUMER_CONTRACT_VERSION,
    SB_TO_SL_ALLOWED_FIELDS,
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
from .corpus_compilation_proxy import build_corpus_compilation_proxy


# Load the stable compiler first so the graph bridge can retain its exact data
# classes and function globals.  Then replace the public module entry with a
# forwarding proxy.  Direct imports, package imports and the tranche runner's
# legacy-first import order now select the same graph-enabled compiler surface.
_legacy_corpus_compilation = importlib.import_module(".corpus_compilation", __name__)
_graph_corpus_compilation = importlib.import_module(
    ".graph_optimal_corpus_compilation", __name__
)
corpus_compilation = build_corpus_compilation_proxy(
    _legacy_corpus_compilation,
    overrides={
        "_semantic_annotation_layer": (
            _graph_corpus_compilation._semantic_annotation_layer
        ),
        "DOCUMENT_GRAPH_PROJECTION_CONTRACT": (
            _graph_corpus_compilation.DOCUMENT_GRAPH_PROJECTION_CONTRACT
        ),
        "GRAPH_OPTIMAL_CORPUS_COMPILATION_CONTRACT": (
            _graph_corpus_compilation.GRAPH_OPTIMAL_CORPUS_COMPILATION_CONTRACT
        ),
        "graph_execution_contract": _graph_corpus_compilation.graph_execution_contract,
    },
)
sys.modules[f"{__name__}.corpus_compilation"] = corpus_compilation


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
    "corpus_compilation",
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
