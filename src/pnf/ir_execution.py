"""Fail-closed execution receipts over projected Domain IR.

Execution requires both an operationally valid Domain IR and explicit
applicability witnesses. Semantic similarity, projection success, or a typed
meet alone cannot execute a rule, query, or action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from src.pnf.domain_ir import DomainIRProjection, refs
from src.policy.carriers.canonical import canonical_sha256

IR_EXECUTION_REQUEST_SCHEMA_VERSION = "sl.pnf.ir_execution_request.v0_1"
IR_EXECUTION_RECEIPT_SCHEMA_VERSION = "sl.pnf.ir_execution_receipt.v0_1"

_OUTCOMES = {
    "executed",
    "refused_invalid_ir",
    "refused_missing_applicability",
    "blocked_missing_evidence",
    "superseded",
}


def _get(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, Mapping) else getattr(
        value, name, default
    )


def _ir_ref(value: Any) -> str:
    return str(
        _get(value, "domain_ir_ref", "")
        or (value.domain_ir_ref if isinstance(value, DomainIRProjection) else "")
    )


@dataclass(frozen=True)
class IRExecutionRequest:
    document_ref: str
    domain_ir_ref: str
    rule_or_query_ref: str
    applicability_witness_refs: tuple[str, ...]
    required_evidence_refs: tuple[str, ...] = ()
    supplied_evidence_refs: tuple[str, ...] = ()
    requested_output: Mapping[str, Any] | None = None
    supersedes_request_ref: str | None = None
    request_revision: str = "v0_1"

    @property
    def request_ref(self) -> str:
        return "ir-execution-request:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": IR_EXECUTION_REQUEST_SCHEMA_VERSION,
            **asdict(self),
            "applicability_witness_refs": list(
                refs(self.applicability_witness_refs)
            ),
            "required_evidence_refs": list(refs(self.required_evidence_refs)),
            "supplied_evidence_refs": list(refs(self.supplied_evidence_refs)),
            "requested_output": dict(self.requested_output or {}),
            "authority": "execution_request_only",
            "semantic_similarity_executes": False,
        }
        if include_ref:
            payload["request_ref"] = self.request_ref
        return payload


@dataclass(frozen=True)
class IRExecutionReceipt:
    document_ref: str
    request_ref: str
    domain_ir_ref: str
    rule_or_query_ref: str
    applicability_witness_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    outcome: str
    emitted_output: Mapping[str, Any] | None
    reason_chain: tuple[str, ...]
    execution_revision: str = "v0_1"

    def __post_init__(self) -> None:
        if self.outcome not in _OUTCOMES:
            raise ValueError("unsupported IR execution outcome")
        if self.outcome == "executed" and not self.applicability_witness_refs:
            raise ValueError("execution requires an applicability witness")

    @property
    def receipt_ref(self) -> str:
        return "ir-execution-receipt:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": IR_EXECUTION_RECEIPT_SCHEMA_VERSION,
            **asdict(self),
            "applicability_witness_refs": list(
                refs(self.applicability_witness_refs)
            ),
            "evidence_refs": list(refs(self.evidence_refs)),
            "emitted_output": dict(self.emitted_output or {}),
            "reason_chain": list(self.reason_chain),
            "applicability_witnessed": bool(self.applicability_witness_refs),
            "semantic_similarity_executes": False,
            "identity_promoted": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["receipt_ref"] = self.receipt_ref
        return payload


def coerce_execution_request(
    value: IRExecutionRequest | Mapping[str, Any],
) -> IRExecutionRequest:
    if isinstance(value, IRExecutionRequest):
        return value
    return IRExecutionRequest(
        document_ref=str(value["document_ref"]),
        domain_ir_ref=str(value["domain_ir_ref"]),
        rule_or_query_ref=str(value["rule_or_query_ref"]),
        applicability_witness_refs=refs(
            value.get("applicability_witness_refs") or ()
        ),
        required_evidence_refs=refs(value.get("required_evidence_refs") or ()),
        supplied_evidence_refs=refs(value.get("supplied_evidence_refs") or ()),
        requested_output=(
            dict(value["requested_output"])
            if isinstance(value.get("requested_output"), Mapping)
            else None
        ),
        supersedes_request_ref=(
            str(value["supersedes_request_ref"])
            if value.get("supersedes_request_ref")
            else None
        ),
        request_revision=str(value.get("request_revision") or "v0_1"),
    )


def execute_ir_request(
    *,
    request: IRExecutionRequest | Mapping[str, Any],
    domain_ir: DomainIRProjection | Mapping[str, Any] | None,
) -> IRExecutionReceipt:
    row = coerce_execution_request(request)
    if row.supersedes_request_ref:
        return IRExecutionReceipt(
            document_ref=row.document_ref,
            request_ref=row.request_ref,
            domain_ir_ref=row.domain_ir_ref,
            rule_or_query_ref=row.rule_or_query_ref,
            applicability_witness_refs=(),
            evidence_refs=row.supplied_evidence_refs,
            outcome="superseded",
            emitted_output=None,
            reason_chain=(f"superseded_request:{row.supersedes_request_ref}",),
        )
    if domain_ir is None or _ir_ref(domain_ir) != row.domain_ir_ref:
        return IRExecutionReceipt(
            document_ref=row.document_ref,
            request_ref=row.request_ref,
            domain_ir_ref=row.domain_ir_ref,
            rule_or_query_ref=row.rule_or_query_ref,
            applicability_witness_refs=(),
            evidence_refs=row.supplied_evidence_refs,
            outcome="blocked_missing_evidence",
            emitted_output=None,
            reason_chain=("domain_ir_not_available",),
        )
    validation_state = str(
        _get(domain_ir, "validation_state", "operational_candidate")
        or "operational_candidate"
    )
    if validation_state not in {"operational_candidate", "operationally_valid"}:
        return IRExecutionReceipt(
            document_ref=row.document_ref,
            request_ref=row.request_ref,
            domain_ir_ref=row.domain_ir_ref,
            rule_or_query_ref=row.rule_or_query_ref,
            applicability_witness_refs=(),
            evidence_refs=row.supplied_evidence_refs,
            outcome="refused_invalid_ir",
            emitted_output=None,
            reason_chain=(f"invalid_domain_ir:{validation_state}",),
        )
    if not row.applicability_witness_refs:
        return IRExecutionReceipt(
            document_ref=row.document_ref,
            request_ref=row.request_ref,
            domain_ir_ref=row.domain_ir_ref,
            rule_or_query_ref=row.rule_or_query_ref,
            applicability_witness_refs=(),
            evidence_refs=row.supplied_evidence_refs,
            outcome="refused_missing_applicability",
            emitted_output=None,
            reason_chain=(
                "valid_ir_is_not_an_applicability_witness",
                "semantic_similarity_alone_cannot_execute",
            ),
        )
    missing = set(row.required_evidence_refs) - set(row.supplied_evidence_refs)
    if missing:
        return IRExecutionReceipt(
            document_ref=row.document_ref,
            request_ref=row.request_ref,
            domain_ir_ref=row.domain_ir_ref,
            rule_or_query_ref=row.rule_or_query_ref,
            applicability_witness_refs=row.applicability_witness_refs,
            evidence_refs=row.supplied_evidence_refs,
            outcome="blocked_missing_evidence",
            emitted_output=None,
            reason_chain=tuple(
                f"missing_evidence:{ref}" for ref in sorted(missing)
            ),
        )
    return IRExecutionReceipt(
        document_ref=row.document_ref,
        request_ref=row.request_ref,
        domain_ir_ref=row.domain_ir_ref,
        rule_or_query_ref=row.rule_or_query_ref,
        applicability_witness_refs=row.applicability_witness_refs,
        evidence_refs=refs(
            (*row.supplied_evidence_refs, *_get(domain_ir, "provenance_refs", ()))
        ),
        outcome="executed",
        emitted_output=dict(row.requested_output or {}),
        reason_chain=(
            "domain_ir_operationally_valid",
            "applicability_witness_present",
            "required_evidence_present",
        ),
    )


def execute_ir_requests(
    *,
    requests: Sequence[IRExecutionRequest | Mapping[str, Any]],
    domain_ir: Sequence[DomainIRProjection | Mapping[str, Any]],
) -> tuple[IRExecutionReceipt, ...]:
    by_ref = {_ir_ref(row): row for row in domain_ir if _ir_ref(row)}
    return tuple(
        sorted(
            (
                execute_ir_request(
                    request=request,
                    domain_ir=by_ref.get(
                        coerce_execution_request(request).domain_ir_ref
                    ),
                )
                for request in requests
            ),
            key=lambda row: row.receipt_ref,
        )
    )


__all__ = [
    "IRExecutionReceipt",
    "IRExecutionRequest",
    "coerce_execution_request",
    "execute_ir_request",
    "execute_ir_requests",
]
