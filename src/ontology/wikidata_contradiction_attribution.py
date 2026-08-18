from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


CROSS_ONTOLOGY_ATTRIBUTION_SCHEMA_VERSION = "wikidata_cross_ontology_attribution/v1"
ATTRIBUTION_LAYERS = ("source", "transcription", "alignment", "target")


@dataclass(frozen=True)
class EvidenceSquare:
    supports: bool
    refutes: bool

    @property
    def corner(self) -> str:
        if self.supports and self.refutes:
            return "both"
        if self.supports:
            return "support-only"
        if self.refutes:
            return "refute-only"
        return "neither"

    @property
    def trit(self) -> str:
        if self.supports and not self.refutes:
            return "supported"
        if self.refutes and not self.supports:
            return "contradicted"
        return "unresolved"

    def merge(self, other: "EvidenceSquare") -> "EvidenceSquare":
        return EvidenceSquare(
            supports=self.supports or other.supports,
            refutes=self.refutes or other.refutes,
        )


@dataclass(frozen=True)
class LayerEvidence:
    square: EvidenceSquare
    evidence: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()


def _layer_payload(layer: LayerEvidence) -> dict[str, Any]:
    return {
        "support_square": asdict(layer.square),
        "corner": layer.square.corner,
        "trit_projection": layer.square.trit,
        "evidence": list(layer.evidence),
        "provenance": list(layer.provenance),
        "obligations": list(layer.obligations),
    }


def _required_resolution(layers: Mapping[str, LayerEvidence], required_layers: tuple[str, ...]) -> str:
    required = [layers[name].square for name in required_layers]
    if any(square.corner == "neither" for square in required):
        return "unresolved-required-axis"
    pooled = EvidenceSquare(False, False)
    for square in required:
        pooled = pooled.merge(square)
    if pooled.corner == "both":
        return "conflict"
    if all(square.corner == "support-only" for square in required):
        return "supported"
    if all(square.corner == "refute-only" for square in required):
        return "contradicted"
    return "unresolved-mixed"


def build_cross_ontology_attribution(
    *,
    claim_id: str,
    claim_surface: str,
    source: LayerEvidence,
    transcription: LayerEvidence,
    alignment: LayerEvidence,
    target: LayerEvidence,
    required_layers: tuple[str, ...] = ATTRIBUTION_LAYERS,
) -> dict[str, Any]:
    """Build the runtime handoff consumed by DASHI-style derivation fibres.

    Evidence is pooled on the two-bit support square before any three-valued
    presentation.  Required-axis completeness is evaluated separately: a
    support-only source cannot manufacture a resolved end-to-end verdict when
    a required transcription/alignment/target axis has no evidence.
    """

    layers = {
        "source": source,
        "transcription": transcription,
        "alignment": alignment,
        "target": target,
    }
    unknown = sorted(set(required_layers) - set(ATTRIBUTION_LAYERS))
    if unknown:
        raise ValueError(f"unknown attribution layers: {', '.join(unknown)}")

    pooled = EvidenceSquare(False, False)
    for name in ATTRIBUTION_LAYERS:
        pooled = pooled.merge(layers[name].square)

    return {
        "schema_version": CROSS_ONTOLOGY_ATTRIBUTION_SCHEMA_VERSION,
        "claim_id": claim_id,
        "claim_surface": claim_surface,
        "layers": {name: _layer_payload(layers[name]) for name in ATTRIBUTION_LAYERS},
        "required_layers": list(required_layers),
        "pooled_support_square": asdict(pooled),
        "pooled_corner": pooled.corner,
        "pooled_trit_projection": pooled.trit,
        "required_resolution": _required_resolution(layers, required_layers),
        "non_promotion_boundary": [
            "neither on a required axis is unresolved, not refutation",
            "both and neither both project to trit=unresolved but remain distinct support squares",
            "bounded graph diagnostics remain candidate evidence until acquisition completeness for the scoped claim is established",
            "runtime attribution is review evidence and does not create edit or world-truth authority",
        ],
    }


def target_evidence_from_disjoint_union_report(
    report: Mapping[str, Any],
    *,
    spec_id: str,
    bounded_result_authoritative: bool = False,
) -> LayerEvidence:
    """Convert one bounded target diagnostic into an attribution-layer square.

    Default behaviour is deliberately conservative.  A bounded slice may omit
    a P279/P31 fact that exists in the target graph, so neither a pass nor a
    failure is promoted to target ontology support/refutation unless the caller
    explicitly certifies that this bounded result is authoritative for the
    scoped claim.
    """

    specs = {
        str(row.get("spec_id")): row
        for row in report.get("disjoint_unions", [])
        if isinstance(row, Mapping)
    }
    row = specs.get(spec_id)
    if row is None:
        return LayerEvidence(
            EvidenceSquare(False, False),
            obligations=(f"no finite-KB disjoint-union result for {spec_id}",),
        )

    provenance = (str(report.get("source_window_id", "")),)
    if not bounded_result_authoritative:
        finite_ok = bool(row.get("finite_dun_ok"))
        return LayerEvidence(
            EvidenceSquare(False, False),
            evidence=(f"bounded finite_dun_ok={str(finite_ok).lower()} for {spec_id}",),
            provenance=provenance,
            obligations=(
                "establish acquisition completeness for the scoped P2738/P11260/P279/P31 claim before promoting the bounded target result",
            ),
        )

    if bool(row.get("finite_dun_ok")):
        return LayerEvidence(
            EvidenceSquare(True, False),
            evidence=(f"authoritative finite disjoint-union obligations pass for {spec_id}",),
            provenance=provenance,
        )

    failures = []
    for field in (
        "component_not_subclass_count",
        "union_exhaustivity_failure_count",
        "pairwise_disjointness_failure_count",
    ):
        value = int(row.get(field, 0) or 0)
        if value:
            failures.append(f"{field}={value}")
    return LayerEvidence(
        EvidenceSquare(False, True),
        evidence=tuple(failures),
        provenance=provenance,
    )


__all__ = [
    "ATTRIBUTION_LAYERS",
    "CROSS_ONTOLOGY_ATTRIBUTION_SCHEMA_VERSION",
    "EvidenceSquare",
    "LayerEvidence",
    "build_cross_ontology_attribution",
    "target_evidence_from_disjoint_union_report",
]
