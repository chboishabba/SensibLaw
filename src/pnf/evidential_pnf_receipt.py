"""Stable bridge receipt from SensibLaw numeric PNF to evidential PNF review.

This module deliberately does *not* infer quantifier force, causal force, scope,
or world truth.  It exports the source-anchored computational facts needed by a
separate reviewed correspondence layer (for example DASHI's
``SensibLawSpacyPredicateNormalFormBridgeExact``).

The receipt preserves the strict numeric-PNF boundary:

    spaCy observation -> owned sentence/numeric PNF -> document interface
      -> residual demands -> reviewed evidential interpretation

A closed numeric document interface is not world closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


EVIDENTIAL_PNF_BRIDGE_SCHEMA_VERSION = "sl.evidential_pnf_bridge.v0_1"


@dataclass(frozen=True, slots=True)
class EvidentialPNFBridgeReceipt:
    schema_version: str
    run_ref: str
    document_ref: str
    canonical_text_sha256: str
    parser_contract_ref: str
    numeric_pnf_compiler_contract_ref: str
    graph_ref: str
    residual_demand_refs: tuple[str, ...]
    representation: str
    world_resolution_deferred: bool
    cross_document_identity_closed: bool
    legacy_document_materialisation: bool
    parser_observation_is_semantic_authority: bool
    semantic_correspondence_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_ref": self.run_ref,
            "document_ref": self.document_ref,
            "canonical_text_sha256": self.canonical_text_sha256,
            "parser_contract_ref": self.parser_contract_ref,
            "numeric_pnf_compiler_contract_ref": self.numeric_pnf_compiler_contract_ref,
            "graph_ref": self.graph_ref,
            "residual_demand_refs": list(self.residual_demand_refs),
            "representation": self.representation,
            "world_resolution_deferred": self.world_resolution_deferred,
            "cross_document_identity_closed": self.cross_document_identity_closed,
            "legacy_document_materialisation": self.legacy_document_materialisation,
            "parser_observation_is_semantic_authority": self.parser_observation_is_semantic_authority,
            "semantic_correspondence_required": self.semantic_correspondence_required,
        }


def _required_text(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing non-empty {key}")
    return value


def _string_tuple(values: Sequence[Any], key: str) -> tuple[str, ...]:
    result = tuple(str(value) for value in values)
    if any(not value for value in result):
        raise ValueError(f"{key} contains an empty reference")
    return result


def build_evidential_pnf_bridge_receipt(
    *,
    compilation_artifacts: Mapping[str, Any],
    canonical_text_sha256: str,
) -> EvidentialPNFBridgeReceipt:
    """Project strict numeric-PNF artifacts to a non-semantic bridge receipt.

    ``compilation_artifacts`` is the artifact mapping emitted by
    ``compile_numeric_pnf_document``.  The projection intentionally rejects any
    artifact claiming world closure or cross-document identity closure: those
    stages belong to later source/world resolution, not the document parser.
    """

    authority_raw = compilation_artifacts.get("numeric_pnf_authority")
    phase_raw = compilation_artifacts.get("phase_boundary")
    if not isinstance(authority_raw, Mapping):
        raise ValueError("numeric_pnf_authority artifact is required")
    if not isinstance(phase_raw, Mapping):
        raise ValueError("phase_boundary artifact is required")

    world_resolution_deferred = bool(authority_raw.get("world_resolution_deferred"))
    cross_document_identity_closed = bool(phase_raw.get("cross_document_identity_closed"))
    legacy_materialisation = bool(authority_raw.get("legacy_document_materialisation"))

    if not world_resolution_deferred:
        raise ValueError("numeric PNF bridge requires world resolution to remain deferred")
    if cross_document_identity_closed:
        raise ValueError("document numeric PNF may not claim cross-document identity closure")
    if legacy_materialisation:
        raise ValueError("strict numeric PNF bridge may not require legacy document materialisation")

    demand_values = authority_raw.get("demand_refs", ())
    if not isinstance(demand_values, (list, tuple)):
        raise ValueError("numeric PNF demand_refs must be a sequence")

    return EvidentialPNFBridgeReceipt(
        schema_version=EVIDENTIAL_PNF_BRIDGE_SCHEMA_VERSION,
        run_ref=_required_text(authority_raw, "run_ref"),
        document_ref=_required_text(authority_raw, "document_ref"),
        canonical_text_sha256=str(canonical_text_sha256),
        parser_contract_ref=_required_text(authority_raw, "parser_execution_contract_ref"),
        numeric_pnf_compiler_contract_ref=_required_text(authority_raw, "compiler_contract_ref"),
        graph_ref=_required_text(authority_raw, "graph_ref"),
        residual_demand_refs=_string_tuple(demand_values, "demand_refs"),
        representation=_required_text(authority_raw, "representation"),
        world_resolution_deferred=world_resolution_deferred,
        cross_document_identity_closed=cross_document_identity_closed,
        legacy_document_materialisation=legacy_materialisation,
        parser_observation_is_semantic_authority=False,
        semantic_correspondence_required=True,
    )


__all__ = [
    "EVIDENTIAL_PNF_BRIDGE_SCHEMA_VERSION",
    "EvidentialPNFBridgeReceipt",
    "build_evidential_pnf_bridge_receipt",
]
