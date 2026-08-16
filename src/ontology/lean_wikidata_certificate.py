from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.ontology.lean_wikidata_source_contract import (
    ARISTOTLE_REQUEST_ID,
    checker_contract_is_source_backed,
)


CONTRACT = "sensiblaw.lean_wikidata_certificate.v0_1"

RELATION_KINDS = frozenset(
    {
        "instance_of",
        "subclass_of",
        "union_of",
        "intersection_of",
        "disjoint_union_of",
        "disjoint_with",
        "equivalent_class",
        "rdf_entailment",
    }
)

EPISTEMIC_STATES = frozenset({"supported", "unresolved", "contradicted"})


class LeanCertificateError(ValueError):
    """Raised when an imported theorem/checker certificate is malformed."""


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LeanCertificateError(f"{key} must be a non-empty string")
    return value.strip()


def _required_bool(row: Mapping[str, Any], key: str) -> bool:
    value = row.get(key)
    if not isinstance(value, bool):
        raise LeanCertificateError(f"{key} must be a boolean")
    return value


def _string_tuple(value: Any, *, key: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise LeanCertificateError(f"{key} must be a list of strings")
    result: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise LeanCertificateError(f"{key} entries must be non-empty strings")
        result.append(entry.strip())
    return tuple(result)


@dataclass(frozen=True)
class LeanOntologyCertificate:
    request_id: str
    module_name: str
    theorem_name: str
    checker_name: str
    source_snapshot: str
    subject_ref: str
    predicate_ref: str
    object_ref: str
    relation_kind: str
    source_references: tuple[str, ...]
    checker_accepted: bool
    theorem_backed: bool

    @property
    def epistemic_state(self) -> str:
        """Project a positive source-backed checker result into evidence state."""
        if self.checker_accepted and self.theorem_backed:
            return "supported"
        return "unresolved"

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "LeanOntologyCertificate":
        relation_kind = _required_text(row, "relation_kind")
        if relation_kind not in RELATION_KINDS:
            allowed = ", ".join(sorted(RELATION_KINDS))
            raise LeanCertificateError(
                f"relation_kind must be one of: {allowed}; got {relation_kind!r}"
            )

        request_id = _required_text(row, "request_id")
        module_name = _required_text(row, "module_name")
        theorem_name = _required_text(row, "theorem_name")
        checker_name = _required_text(row, "checker_name")
        theorem_backed = _required_bool(row, "theorem_backed")

        if theorem_backed:
            if request_id != ARISTOTLE_REQUEST_ID:
                raise LeanCertificateError(
                    "theorem_backed certificate request_id does not match the pinned source snapshot"
                )
            if not checker_contract_is_source_backed(
                relation_kind=relation_kind,
                module_name=module_name,
                checker_name=checker_name,
                theorem_name=theorem_name,
            ):
                raise LeanCertificateError(
                    "theorem_backed certificate does not match a checker/theorem pair in the pinned Lean source"
                )

        return cls(
            request_id=request_id,
            module_name=module_name,
            theorem_name=theorem_name,
            checker_name=checker_name,
            source_snapshot=_required_text(row, "source_snapshot"),
            subject_ref=_required_text(row, "subject_ref"),
            predicate_ref=_required_text(row, "predicate_ref"),
            object_ref=_required_text(row, "object_ref"),
            relation_kind=relation_kind,
            source_references=_string_tuple(
                row.get("source_references"), key="source_references"
            ),
            checker_accepted=_required_bool(row, "checker_accepted"),
            theorem_backed=theorem_backed,
        )

    def to_receipt(self) -> dict[str, Any]:
        return {
            "contract": CONTRACT,
            "request_id": self.request_id,
            "module_name": self.module_name,
            "theorem_name": self.theorem_name,
            "checker_name": self.checker_name,
            "source_snapshot": self.source_snapshot,
            "subject_ref": self.subject_ref,
            "predicate_ref": self.predicate_ref,
            "object_ref": self.object_ref,
            "relation_kind": self.relation_kind,
            "source_references": list(self.source_references),
            "checker_accepted": self.checker_accepted,
            "theorem_backed": self.theorem_backed,
            "epistemic_state": self.epistemic_state,
            "truth_authority": False,
            "edit_authority": False,
        }


@dataclass(frozen=True)
class CrossOntologyRelationComparison:
    certificate: LeanOntologyCertificate
    external_state: str
    external_references: tuple[str, ...]

    @property
    def disposition(self) -> str:
        local = self.certificate.epistemic_state
        external = self.external_state
        if local == "supported" and external == "supported":
            return "replicated"
        if (local, external) in {
            ("supported", "contradicted"),
            ("contradicted", "supported"),
        }:
            return "conflicting"
        return "unresolved"

    def to_receipt(self) -> dict[str, Any]:
        return {
            "contract": "sensiblaw.cross_ontology_relation_comparison.v0_1",
            "lean_certificate": self.certificate.to_receipt(),
            "external_state": self.external_state,
            "external_references": list(self.external_references),
            "disposition": self.disposition,
            "truth_authority": False,
            "edit_authority": False,
        }


def compare_external_relation(
    certificate: LeanOntologyCertificate,
    *,
    external_state: str,
    external_references: Iterable[str] = (),
) -> CrossOntologyRelationComparison:
    if external_state not in EPISTEMIC_STATES:
        allowed = ", ".join(sorted(EPISTEMIC_STATES))
        raise LeanCertificateError(
            f"external_state must be one of: {allowed}; got {external_state!r}"
        )
    refs = tuple(external_references)
    if not all(isinstance(ref, str) and ref.strip() for ref in refs):
        raise LeanCertificateError("external_references entries must be non-empty strings")
    return CrossOntologyRelationComparison(
        certificate=certificate,
        external_state=external_state,
        external_references=tuple(ref.strip() for ref in refs),
    )


def load_certificate_packet(payload: Mapping[str, Any]) -> list[LeanOntologyCertificate]:
    """Load a deterministic certificate packet exported by the pinned Lean source."""
    if payload.get("contract") != CONTRACT:
        raise LeanCertificateError(f"unsupported certificate contract: {payload.get('contract')!r}")
    raw = payload.get("certificates")
    if not isinstance(raw, list):
        raise LeanCertificateError("certificates must be a list")
    certificates: list[LeanOntologyCertificate] = []
    for index, row in enumerate(raw):
        if not isinstance(row, Mapping):
            raise LeanCertificateError(f"certificates[{index}] must be an object")
        certificates.append(LeanOntologyCertificate.from_mapping(row))
    return certificates
