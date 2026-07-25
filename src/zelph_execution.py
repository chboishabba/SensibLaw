"""Generic Zelph execution/output receipt.

Engine transport success is not semantic output success.  Callers must branch on
``outcome`` and required predicates before emitting a successful handoff.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from src.policy.carriers.canonical import canonical_sha256

ZELPH_EXECUTION_RECEIPT_VERSION = "sl.zelph.execution_receipt.v0_1"
_OUTCOMES = {
    "engine_unavailable",
    "engine_failed",
    "blocked_input",
    "executed_no_match",
    "executed_with_output",
    "failed_required_output",
}


def _refs(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class ZelphExecutionReceipt:
    profile_ref: str
    outcome: str
    engine_status: str
    emitted_predicates: tuple[str, ...]
    required_predicates: tuple[str, ...]
    missing_required_predicates: tuple[str, ...]
    output_refs: tuple[str, ...]
    reason_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.outcome not in _OUTCOMES:
            raise ValueError("unsupported Zelph execution outcome")
        if self.outcome == "executed_with_output" and self.missing_required_predicates:
            raise ValueError("successful Zelph output cannot omit required predicates")

    @property
    def receipt_ref(self) -> str:
        return "zelph-execution:" + canonical_sha256(self.to_dict(include_ref=False))

    @property
    def successful_handoff(self) -> bool:
        return self.outcome == "executed_with_output" and not self.missing_required_predicates

    @property
    def ok(self) -> bool:
        """Deprecated presentation compatibility; never authoritative."""
        return self.successful_handoff

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": ZELPH_EXECUTION_RECEIPT_VERSION,
            **asdict(self),
            "emitted_predicates": list(_refs(self.emitted_predicates)),
            "required_predicates": list(_refs(self.required_predicates)),
            "missing_required_predicates": list(_refs(self.missing_required_predicates)),
            "output_refs": list(_refs(self.output_refs)),
            "reason_refs": list(_refs(self.reason_refs)),
            "successful_handoff": self.successful_handoff,
            "ok": self.ok,
            "ok_is_deprecated_derived_compatibility": True,
        }
        if include_ref:
            payload["receipt_ref"] = self.receipt_ref
        return payload


def assess_zelph_execution(
    *,
    profile_ref: str,
    engine_payload: Mapping[str, Any] | None,
    required_predicates: Iterable[str] = (),
    input_block_reasons: Iterable[str] = (),
) -> ZelphExecutionReceipt:
    required = _refs(required_predicates)
    blocked = _refs(input_block_reasons)
    if blocked:
        return ZelphExecutionReceipt(
            profile_ref=profile_ref,
            outcome="blocked_input",
            engine_status="not_executed",
            emitted_predicates=(),
            required_predicates=required,
            missing_required_predicates=required,
            output_refs=(),
            reason_refs=blocked,
        )
    if engine_payload is None:
        return ZelphExecutionReceipt(
            profile_ref=profile_ref,
            outcome="engine_unavailable",
            engine_status="unavailable",
            emitted_predicates=(),
            required_predicates=required,
            missing_required_predicates=required,
            output_refs=(),
            reason_refs=("engine_payload_absent",),
        )
    status = str(engine_payload.get("status") or "unknown")
    if status in {"error", "failed", "exception"}:
        return ZelphExecutionReceipt(
            profile_ref=profile_ref,
            outcome="engine_failed",
            engine_status=status,
            emitted_predicates=(),
            required_predicates=required,
            missing_required_predicates=required,
            output_refs=(),
            reason_refs=_refs(engine_payload.get("errors") or ("engine_failure",)),
        )
    rows = engine_payload.get("results") or engine_payload.get("triples") or engine_payload.get("output") or ()
    emitted: set[str] = set()
    output_refs: list[str] = []
    if isinstance(rows, Mapping):
        rows = rows.get("triples") or rows.get("results") or ()
    for index, row in enumerate(rows if isinstance(rows, (list, tuple)) else ()):
        if isinstance(row, Mapping):
            predicate = str(row.get("predicate") or row.get("predicate_key") or "").strip()
            output_ref = str(row.get("output_ref") or row.get("triple_ref") or f"zelph-output:{index}")
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            predicate = str(row[1]).strip()
            output_ref = f"zelph-output:{index}"
        else:
            continue
        if predicate:
            emitted.add(predicate)
        output_refs.append(output_ref)
    missing = tuple(sorted(set(required) - emitted))
    if missing:
        outcome = "failed_required_output"
        reasons = tuple(f"missing-required-predicate:{value}" for value in missing)
    elif emitted:
        outcome = "executed_with_output"
        reasons = ()
    else:
        outcome = "executed_no_match"
        reasons = ("no_emitted_triples",)
    return ZelphExecutionReceipt(
        profile_ref=profile_ref,
        outcome=outcome,
        engine_status=status,
        emitted_predicates=tuple(sorted(emitted)),
        required_predicates=required,
        missing_required_predicates=missing,
        output_refs=tuple(output_refs),
        reason_refs=reasons,
    )


__all__ = [
    "ZELPH_EXECUTION_RECEIPT_VERSION",
    "ZelphExecutionReceipt",
    "assess_zelph_execution",
]
