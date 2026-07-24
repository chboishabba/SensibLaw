"""Deterministic identity and non-promotion certificates for Legal IR parity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from src.policy.carriers.canonical import canonical_sha256

LEGAL_IR_PARITY_CONTRACT = "curated-legal-ir-parity:v0_1"


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class SemanticIdentitySnapshot:
    proposal_refs: tuple[str, ...] = ()
    factor_refs: tuple[str, ...] = ()
    graph_refs: tuple[str, ...] = ()
    fibre_ledger_refs: tuple[str, ...] = ()
    residual_refs: tuple[str, ...] = ()
    demand_refs: tuple[str, ...] = ()
    legal_ir_refs: tuple[str, ...] = ()
    typed_meet_refs: tuple[str, ...] = ()
    legacy_witness_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(self, field_name, _refs(getattr(self, field_name)))

    @property
    def snapshot_ref(self) -> str:
        return "semantic-identity-snapshot:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_ref": self.snapshot_ref, **asdict(self)}


@dataclass(frozen=True)
class IdentityParityResult:
    control_snapshot_ref: str
    candidate_snapshot_ref: str
    identical: bool
    added_refs: Mapping[str, tuple[str, ...]]
    removed_refs: Mapping[str, tuple[str, ...]]

    @property
    def result_ref(self) -> str:
        return "semantic-identity-parity:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "control_snapshot_ref": self.control_snapshot_ref,
            "candidate_snapshot_ref": self.candidate_snapshot_ref,
            "identical": self.identical,
            "added_refs": {key: list(value) for key, value in sorted(self.added_refs.items())},
            "removed_refs": {key: list(value) for key, value in sorted(self.removed_refs.items())},
        }
        return {"result_ref": self.result_ref, **payload} if include_ref else payload


def compare_identity_snapshots(
    control: SemanticIdentitySnapshot,
    candidate: SemanticIdentitySnapshot,
) -> IdentityParityResult:
    added: dict[str, tuple[str, ...]] = {}
    removed: dict[str, tuple[str, ...]] = {}
    for field_name in control.__dataclass_fields__:
        before = set(getattr(control, field_name))
        after = set(getattr(candidate, field_name))
        if after - before:
            added[field_name] = tuple(sorted(after - before))
        if before - after:
            removed[field_name] = tuple(sorted(before - after))
    return IdentityParityResult(
        control_snapshot_ref=control.snapshot_ref,
        candidate_snapshot_ref=candidate.snapshot_ref,
        identical=not added and not removed,
        added_refs=added,
        removed_refs=removed,
    )


def snapshot_from_build_artifacts(
    artifacts: Iterable[Mapping[str, Any]],
    *,
    legal_ir_refs: Iterable[str] = (),
    typed_meet_refs: Iterable[str] = (),
    legacy_witness_refs: Iterable[str] = (),
) -> SemanticIdentitySnapshot:
    proposal_refs: list[str] = []
    factor_refs: list[str] = []
    graph_refs: list[str] = []
    fibre_ledger_refs: list[str] = []
    residual_refs: list[str] = []
    demand_refs: list[str] = []
    for artifact in artifacts:
        graph = artifact.get("pnf_graph") or {}
        if graph.get("graph_ref"):
            graph_refs.append(str(graph["graph_ref"]))
        for factor in graph.get("factors") or ():
            if factor.get("factor_ref"):
                factor_refs.append(str(factor["factor_ref"]))
            residual_refs.extend(str(value) for value in factor.get("residuals") or ())
        streaming = artifact.get("streaming_semantic_build") or {}
        proposal_refs.extend(
            str(row["proposal_ref"])
            for row in streaming.get("proposals") or ()
            if isinstance(row, Mapping) and row.get("proposal_ref")
        )
        if streaming.get("fibre_ledger_ref"):
            fibre_ledger_refs.append(str(streaming["fibre_ledger_ref"]))
        materialized = streaming.get("materialized_reduction") or {}
        residual_refs.extend(
            str(row["residual_ref"])
            for row in materialized.get("residuals") or ()
            if isinstance(row, Mapping) and row.get("residual_ref")
        )
        demand_refs.extend(
            str(row["demand_ref"])
            for row in artifact.get("resolution_demands") or ()
            if isinstance(row, Mapping) and row.get("demand_ref")
        )
    return SemanticIdentitySnapshot(
        proposal_refs=tuple(proposal_refs),
        factor_refs=tuple(factor_refs),
        graph_refs=tuple(graph_refs),
        fibre_ledger_refs=tuple(fibre_ledger_refs),
        residual_refs=tuple(residual_refs),
        demand_refs=tuple(demand_refs),
        legal_ir_refs=tuple(legal_ir_refs),
        typed_meet_refs=tuple(typed_meet_refs),
        legacy_witness_refs=tuple(legacy_witness_refs),
    )


@dataclass(frozen=True)
class CuratedLegalIRParityReceipt:
    corpus_ref: str
    admission_profile_ref: str
    compiler_contract_ref: str
    source_revision_refs: tuple[str, ...]
    ordinary_graph_refs: tuple[str, ...]
    legal_graph_refs: tuple[str, ...]
    demand_refs: tuple[str, ...]
    plan_refs: tuple[str, ...]
    legal_ir_refs: tuple[str, ...]
    typed_meet_refs: tuple[str, ...]
    legacy_witness_refs: tuple[str, ...]
    identity_snapshot: Mapping[str, Any]
    control_snapshot: Mapping[str, Any] | None
    identity_parity: bool | None
    network_attempt_count: int
    unexpected_failure_refs: tuple[str, ...] = ()

    @property
    def receipt_ref(self) -> str:
        return "curated-legal-ir-parity-receipt:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_ref": self.receipt_ref,
            **asdict(self),
            "contract_ref": LEGAL_IR_PARITY_CONTRACT,
            "semantic_state_promoted": False,
            "applicability_closed": False,
            "legal_truth_closed": False,
        }


__all__ = [
    "LEGAL_IR_PARITY_CONTRACT",
    "CuratedLegalIRParityReceipt",
    "IdentityParityResult",
    "SemanticIdentitySnapshot",
    "compare_identity_snapshots",
    "snapshot_from_build_artifacts",
]
