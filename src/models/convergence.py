from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


CONVERGENCE_SCHEMA_VERSION = "sl.world_model_convergence.v0_1"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True)
class SourceUnit:
    source_unit_id: str
    root_artifact_id: str
    source_family: str
    authority_level: str
    verification_status: str
    provenance_chain: dict[str, Any]
    source_state: str = "NORMALIZED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_unit_id": self.source_unit_id,
            "root_artifact_id": self.root_artifact_id,
            "source_family": self.source_family,
            "authority_level": self.authority_level,
            "verification_status": self.verification_status,
            "provenance_chain": dict(self.provenance_chain),
            "source_state": self.source_state,
        }


@dataclass(frozen=True)
class ConvergenceRecord:
    claim_id: str
    convergence_state: str
    normalized_sources: list[dict[str, Any]]
    merged_evidence_basis: dict[str, Any]
    governance_basis: dict[str, Any]
    schema_version: str = CONVERGENCE_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "claim_id": self.claim_id,
            "convergence_state": self.convergence_state,
            "normalized_sources": list(self.normalized_sources),
            "merged_evidence_basis": dict(self.merged_evidence_basis),
            "governance_basis": dict(self.governance_basis),
        }


def build_convergence_record(
    *,
    claim_id: str,
    evidence_paths: Sequence[Mapping[str, Any]],
    independent_root_artifact_ids: Sequence[str],
    claim_status: str,
) -> dict[str, Any]:
    normalized_sources: list[dict[str, Any]] = []
    for path in evidence_paths:
        if not isinstance(path, Mapping):
            continue
        source_unit = SourceUnit(
            source_unit_id=_as_text(path.get("source_unit_id")),
            root_artifact_id=_as_text(path.get("root_artifact_id")),
            source_family=_as_text(path.get("source_family")) or "wikidata_after_state_verification",
            authority_level=_as_text(path.get("authority_level")),
            verification_status=_as_text(path.get("verification_status")),
            provenance_chain=_copy_mapping(path.get("provenance_chain")),
        )
        normalized_sources.append(source_unit.as_dict())

    convergence_state = "RAW"
    if normalized_sources:
        convergence_state = "NORMALIZED"
    if len(normalized_sources) >= 2:
        convergence_state = "MERGED"
    if _as_text(claim_status) in {"PROMOTED", "REPEATED_RUN", "SINGLE_RUN"}:
        convergence_state = "GOVERNED"

    record = ConvergenceRecord(
        claim_id=_as_text(claim_id),
        convergence_state=convergence_state,
        normalized_sources=normalized_sources,
        merged_evidence_basis={
            "source_count": len(normalized_sources),
            "independent_root_artifact_ids": [_as_text(value) for value in independent_root_artifact_ids if _as_text(value)],
        },
        governance_basis={
            "claim_status": _as_text(claim_status),
            "requires_policy_gate": _as_text(claim_status) != "PROMOTED",
        },
    )
    return record.as_dict()
