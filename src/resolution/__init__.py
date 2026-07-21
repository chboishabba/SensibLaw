"""Registry-neutral resolution primitives."""

from .proof_reports import ProofFixture, build_proof_report
from .reconciliation import ReconciliationAssessment, reconcile_meets
from .snapshots import ExternalSnapshotEnvelope

__all__ = [
    "ExternalSnapshotEnvelope",
    "ProofFixture",
    "ReconciliationAssessment",
    "build_proof_report",
    "reconcile_meets",
]
