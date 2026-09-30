"""Runtime parity carrier for source-conditioned atomic legal tests.

This is a narrow SLR analogue of the Agda SourceConditionedAtomicLegalTest /
AtomicCaseRegistry seam. A statute or other legal source defines an exact
atomic proposition; evidence determines the ternary gate.

Gate semantics:
  +1 = positive fit witness exists
   0 = unresolved on the current evidence fibre
  -1 = positive failure witness exists

A citation/source definition never manufactures a case outcome.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable

from src.policy.carriers.canonical import canonical_sha256
from src.pnf.legal_adjunct import LegalTypedMeet

ATOMIC_LEGAL_REGISTRY_CONTRACT = "source-conditioned-atomic-legal-registry:v0_1"
ATOMIC_LEGAL_RESIDUAL_CONTRACT = "atomic-legal-evidence-residual:v0_1"
_VALID_GATES = {-1, 0, 1}


@dataclass(frozen=True)
class AtomicLegalTest:
    proposition_ref: str
    case_ref: str
    legal_system_ref: str
    source_revision_ref: str
    exact_locator: str
    authority_role: str
    subject_ref: str
    gate: int
    positive_witness_refs: tuple[str, ...] = ()
    negative_witness_refs: tuple[str, ...] = ()
    evidence_fibre_ref: str = ""
    test_reference: str = ""

    def __post_init__(self) -> None:
        if not self.proposition_ref:
            raise ValueError("proposition_ref is required")
        if not self.case_ref:
            raise ValueError("case_ref is required")
        if not self.source_revision_ref:
            raise ValueError("source_revision_ref is required")
        if not self.exact_locator:
            raise ValueError("exact_locator is required")
        if self.gate not in _VALID_GATES:
            raise ValueError("gate must be -1, 0, or +1")
        object.__setattr__(
            self, "positive_witness_refs", tuple(sorted(set(self.positive_witness_refs)))
        )
        object.__setattr__(
            self, "negative_witness_refs", tuple(sorted(set(self.negative_witness_refs)))
        )
        if self.gate == 1 and not self.positive_witness_refs:
            raise ValueError("positive gate requires a positive fit witness")
        if self.gate == -1 and not self.negative_witness_refs:
            raise ValueError("negative gate requires a positive failure witness")
        if self.gate == 0 and (self.positive_witness_refs or self.negative_witness_refs):
            raise ValueError("unresolved gate cannot carry directional witnesses")
        if self.positive_witness_refs and self.negative_witness_refs:
            raise ValueError("fit and failure witnesses are mutually exclusive")

    @property
    def registry_key(self) -> tuple[str, str]:
        return (self.case_ref, self.proposition_ref)

    @property
    def test_ref(self) -> str:
        return "atomic-legal-test:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_ref": self.test_ref,
            "contract_ref": ATOMIC_LEGAL_REGISTRY_CONTRACT,
            **asdict(self),
            "citation_creates_case_truth": False,
            "zero_means_unresolved": self.gate == 0,
        }


@dataclass(frozen=True)
class AtomicRegistryReceipt:
    case_ref: str
    tests: tuple[AtomicLegalTest, ...]

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.tests, key=lambda row: row.registry_key))
        object.__setattr__(self, "tests", ordered)
        seen: dict[tuple[str, str], int] = {}
        for test in ordered:
            if test.case_ref != self.case_ref:
                raise ValueError("all registry tests must belong to the same case")
            prior = seen.get(test.registry_key)
            if prior is not None and prior != test.gate:
                raise ValueError(
                    "contradictory atomic gate for exact case/proposition key: "
                    f"{test.registry_key}"
                )
            seen[test.registry_key] = test.gate

    @property
    def receipt_ref(self) -> str:
        return "atomic-legal-registry-receipt:" + canonical_sha256(
            {
                "case_ref": self.case_ref,
                "tests": [row.to_dict() for row in self.tests],
            }
        )

    def gate_for(self, proposition_ref: str) -> int:
        matches = [row.gate for row in self.tests if row.proposition_ref == proposition_ref]
        if not matches:
            raise KeyError(proposition_ref)
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_ref": self.receipt_ref,
            "contract_ref": ATOMIC_LEGAL_REGISTRY_CONTRACT,
            "case_ref": self.case_ref,
            "tests": [row.to_dict() for row in self.tests],
            "one_gate_per_exact_case_proposition": True,
            "registry_creates_authority": False,
            "registry_promotes_legal_truth": False,
        }


@dataclass(frozen=True)
class AtomicEvidenceResidual:
    case_ref: str
    proposition_ref: str
    evidence_fibre_ref: str
    source_revision_ref: str
    exact_locator: str
    disposition: str
    user_side_acquisition_debt: bool
    residual_reference: str

    @property
    def residual_ref(self) -> str:
        return "atomic-legal-residual:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            "residual_ref": self.residual_ref,
            "contract_ref": ATOMIC_LEGAL_RESIDUAL_CONTRACT,
            **asdict(self),
            "gate_state": "unresolved",
            "legal_source_acquisition_required": False,
            "legal_truth_closed": False,
        }


def build_atomic_registry(
    *, case_ref: str, tests: Iterable[AtomicLegalTest]
) -> AtomicRegistryReceipt:
    return AtomicRegistryReceipt(case_ref=case_ref, tests=tuple(tests))


def project_unresolved_atomic_residuals(
    registry: AtomicRegistryReceipt,
    *,
    user_side_acquisition_debt: bool,
    residual_reference: str,
    external_evidence_unavailable: bool,
) -> tuple[AtomicEvidenceResidual, ...]:
    """Project only unresolved case-evidence atoms into typed residuals.

    This intentionally does not emit NormativeInteractionDemand: that owner is
    for legal-source acquisition. Here the legal authority is already present;
    the missing object is case evidence. Reporter-held evidence can therefore
    remain a residual without becoming user-side acquisition work.
    """

    disposition = (
        "blocked_external_evidence_unavailable"
        if external_evidence_unavailable
        else "case_evidence_review_required"
    )
    return tuple(
        AtomicEvidenceResidual(
            case_ref=test.case_ref,
            proposition_ref=test.proposition_ref,
            evidence_fibre_ref=test.evidence_fibre_ref,
            source_revision_ref=test.source_revision_ref,
            exact_locator=test.exact_locator,
            disposition=disposition,
            user_side_acquisition_debt=user_side_acquisition_debt,
            residual_reference=residual_reference,
        )
        for test in registry.tests
        if test.gate == 0
    )


def attach_atomic_residuals_to_typed_meet(
    meet: LegalTypedMeet,
    residuals: Iterable[AtomicEvidenceResidual],
) -> LegalTypedMeet:
    """Attach exact unresolved atomic evidence to the canonical typed meet."""

    refs = tuple(
        sorted(
            set(meet.residual_refs)
            | {residual.residual_ref for residual in residuals}
        )
    )
    return replace(meet, residual_refs=refs)


__all__ = [
    "ATOMIC_LEGAL_REGISTRY_CONTRACT",
    "ATOMIC_LEGAL_RESIDUAL_CONTRACT",
    "AtomicEvidenceResidual",
    "AtomicLegalTest",
    "AtomicRegistryReceipt",
    "attach_atomic_residuals_to_typed_meet",
    "build_atomic_registry",
    "project_unresolved_atomic_residuals",
]
