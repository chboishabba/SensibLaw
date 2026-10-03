from __future__ import annotations

from typing import Any, Iterable, Mapping

NONCONFORMANCE_SCHEMA_VERSION = "sl.gov1.nonconformance.v0_1"
CAPA_SCHEMA_VERSION = "sl.gov1.capa.v0_1"
DEFECT_KINDS = (
    "semantic_mismatch",
    "provenance_loss",
    "authority_leak",
    "scope_leak",
    "privacy_exposure",
    "security_boundary_violation",
    "ui_ambiguity",
    "replay_nondeterminism",
    "performance_regression",
    "hidden_work_amplification",
)


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _refs(values: Iterable[Any], field: str, *, required: bool = True) -> list[str]:
    refs = [str(value).strip() for value in values if str(value).strip()]
    if required and not refs:
        raise ValueError(f"{field} requires at least one ref")
    return refs


def build_nonconformance(
    *,
    nonconformance_ref: str,
    subject_ref: str,
    defect_kind: str,
    requirement_refs: Iterable[Any],
    evidence_refs: Iterable[Any],
    residual_refs: Iterable[Any],
    root_cause_refs: Iterable[Any] = (),
) -> dict[str, Any]:
    kind = _text(defect_kind, "defect_kind")
    if kind not in DEFECT_KINDS:
        raise ValueError(f"unsupported defect_kind: {kind}")
    return {
        "schema_version": NONCONFORMANCE_SCHEMA_VERSION,
        "nonconformance_ref": _text(nonconformance_ref, "nonconformance_ref"),
        "subject_ref": _text(subject_ref, "subject_ref"),
        "defect_kind": kind,
        "requirement_refs": _refs(requirement_refs, "requirement_refs"),
        "evidence_refs": _refs(evidence_refs, "evidence_refs"),
        "residual_refs": _refs(residual_refs, "residual_refs"),
        "root_cause_refs": _refs(root_cause_refs, "root_cause_refs", required=False),
        "creates_semantic_authority": False,
    }


def build_capa_cycle(
    *,
    capa_ref: str,
    nonconformance: Mapping[str, Any],
    define_refs: Iterable[Any],
    measure_refs: Iterable[Any],
    analyse_refs: Iterable[Any],
    improve_refs: Iterable[Any],
    control_refs: Iterable[Any],
) -> dict[str, Any]:
    nc_ref = _text(nonconformance.get("nonconformance_ref"), "nonconformance_ref")
    residuals = _refs(nonconformance.get("residual_refs", []), "original_residual_refs")
    evidence = _refs(nonconformance.get("evidence_refs", []), "original_evidence_refs")
    return {
        "schema_version": CAPA_SCHEMA_VERSION,
        "capa_ref": _text(capa_ref, "capa_ref"),
        "nonconformance_ref": nc_ref,
        "define_refs": _refs(define_refs, "define_refs"),
        "measure_refs": _refs(measure_refs, "measure_refs"),
        "analyse_refs": _refs(analyse_refs, "analyse_refs"),
        "improve_refs": _refs(improve_refs, "improve_refs"),
        "control_refs": _refs(control_refs, "control_refs"),
        "original_residual_refs": residuals,
        "original_evidence_refs": evidence,
        "creates_semantic_authority": False,
        "erases_original_nonconformance": False,
    }


__all__ = [
    "NONCONFORMANCE_SCHEMA_VERSION",
    "CAPA_SCHEMA_VERSION",
    "DEFECT_KINDS",
    "build_nonconformance",
    "build_capa_cycle",
]
