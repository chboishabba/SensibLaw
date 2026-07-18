"""Registry-neutral resolution primitives."""

from .snapshots import ExternalSnapshotEnvelope
from .reconciliation import ReconciliationAssessment, reconcile_meets

__all__ = ["ExternalSnapshotEnvelope", "ReconciliationAssessment", "reconcile_meets"]
