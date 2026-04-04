"""Model classes used throughout the project."""

from .action_policy import ACTION_POLICY_SCHEMA_VERSION, ActionPolicyRecord, build_action_policy_record
from .convergence import CONVERGENCE_SCHEMA_VERSION, ConvergenceRecord, SourceUnit, build_convergence_record
from .conflict import CONFLICT_SCHEMA_VERSION, ConflictSet, build_conflict_set
from .attribution_claims import Attribution, ExtractionRecord, SourceEntity
from .document import Document, DocumentMetadata
from .nat_claim import (
    NAT_CLAIM_SCHEMA_VERSION,
    NatClaim,
    NormalizedClaim,
    build_nat_claim_dict,
    build_nat_claim_from_candidate,
    build_normalized_claim_dict,
    build_normalized_claim_from_candidate,
)
from .temporal import TEMPORAL_SCHEMA_VERSION, TemporalEnvelope, build_temporal_envelope
from .provision import Provision
from .sentence import Sentence
from .numeric_claims import Magnitude, QuantifiedClaim, RangeClaim, RatioClaim, NumericSurface
from .text_span import TextSpan

__all__ = [
    "Attribution",
    "ACTION_POLICY_SCHEMA_VERSION",
    "ActionPolicyRecord",
    "CONVERGENCE_SCHEMA_VERSION",
    "CONFLICT_SCHEMA_VERSION",
    "ConvergenceRecord",
    "ConflictSet",
    "Document",
    "DocumentMetadata",
    "ExtractionRecord",
    "Magnitude",
    "NAT_CLAIM_SCHEMA_VERSION",
    "NatClaim",
    "NormalizedClaim",
    "NumericSurface",
    "Provision",
    "QuantifiedClaim",
    "RangeClaim",
    "RatioClaim",
    "Sentence",
    "SourceUnit",
    "SourceEntity",
    "TextSpan",
    "TEMPORAL_SCHEMA_VERSION",
    "TemporalEnvelope",
    "build_action_policy_record",
    "build_convergence_record",
    "build_conflict_set",
    "build_nat_claim_dict",
    "build_nat_claim_from_candidate",
    "build_normalized_claim_dict",
    "build_normalized_claim_from_candidate",
    "build_temporal_envelope",
]
