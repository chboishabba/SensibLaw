"""Content-addressed keys for independently reusable semantic compiler stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.policy.carriers.canonical import canonical_sha256


STAGE_BUILD_KEYS_SCHEMA_VERSION = "sl.pnf.stage_build_keys.v0_1"


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def stage_build_key(
    stage: str,
    *,
    inputs: Iterable[str],
    contract_ref: str,
    declaration_refs: Iterable[str] = (),
    configuration: Mapping[str, Any] | None = None,
) -> str:
    return canonical_sha256(
        {
            "stage": stage,
            "inputs": list(_refs(inputs)),
            "contract_ref": contract_ref,
            "declaration_refs": list(_refs(declaration_refs)),
            "configuration": dict(configuration or {}),
        }
    )


@dataclass(frozen=True)
class StageBuildKeys:
    parser_key: str
    observation_projection_key: str
    base_proposal_key: str
    base_reduction_key: str
    composition_rule_set_key: str
    composition_reduction_key: str
    constraint_fixed_point_key: str
    legal_ir_projection_key: str

    @property
    def bundle_ref(self) -> str:
        return "stage-build-keys:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": STAGE_BUILD_KEYS_SCHEMA_VERSION,
            "parser_key": self.parser_key,
            "observation_projection_key": self.observation_projection_key,
            "base_proposal_key": self.base_proposal_key,
            "base_reduction_key": self.base_reduction_key,
            "composition_rule_set_key": self.composition_rule_set_key,
            "composition_reduction_key": self.composition_reduction_key,
            "constraint_fixed_point_key": self.constraint_fixed_point_key,
            "legal_ir_projection_key": self.legal_ir_projection_key,
        }
        if include_ref:
            payload["bundle_ref"] = self.bundle_ref
        return payload


def derive_stage_build_keys(
    *,
    canonical_text_digest: str,
    parser_contract_ref: str,
    observation_refs: Iterable[str],
    base_proposal_refs: Iterable[str],
    base_factor_refs: Iterable[str],
    declaration_refs: Iterable[str],
    derived_proposal_refs: Iterable[str],
    materialized_factor_refs: Iterable[str],
    constraint_refs: Iterable[str],
    legal_ir_contract_ref: str = "legal-ir-projection:v0_1",
) -> StageBuildKeys:
    parser_key = stage_build_key(
        "parser",
        inputs=(canonical_text_digest,),
        contract_ref=parser_contract_ref,
    )
    observation_projection_key = stage_build_key(
        "observation_projection",
        inputs=(parser_key, *_refs(observation_refs)),
        contract_ref="parser-observation-projection:v0_1",
    )
    base_proposal_key = stage_build_key(
        "base_proposals",
        inputs=(observation_projection_key, *_refs(base_proposal_refs)),
        contract_ref="semantic-base-proposal:v0_1",
    )
    base_reduction_key = stage_build_key(
        "base_reduction",
        inputs=(base_proposal_key, *_refs(base_factor_refs)),
        contract_ref="deterministic-proposal-reduction:v0_1",
    )
    composition_rule_set_key = stage_build_key(
        "composition_rule_set",
        inputs=(base_reduction_key,),
        contract_ref="streaming-composition-worklist:v0_1",
        declaration_refs=declaration_refs,
    )
    composition_reduction_key = stage_build_key(
        "composition_reduction",
        inputs=(
            composition_rule_set_key,
            *_refs(derived_proposal_refs),
            *_refs(materialized_factor_refs),
        ),
        contract_ref="deterministic-proposal-reduction:v0_1",
    )
    constraint_fixed_point_key = stage_build_key(
        "constraint_fixed_point",
        inputs=(composition_reduction_key, *_refs(constraint_refs)),
        contract_ref="constraint-worklist:v0_1",
    )
    legal_ir_projection_key = stage_build_key(
        "legal_ir_projection",
        inputs=(constraint_fixed_point_key,),
        contract_ref=legal_ir_contract_ref,
    )
    return StageBuildKeys(
        parser_key=parser_key,
        observation_projection_key=observation_projection_key,
        base_proposal_key=base_proposal_key,
        base_reduction_key=base_reduction_key,
        composition_rule_set_key=composition_rule_set_key,
        composition_reduction_key=composition_reduction_key,
        constraint_fixed_point_key=constraint_fixed_point_key,
        legal_ir_projection_key=legal_ir_projection_key,
    )


__all__ = [
    "STAGE_BUILD_KEYS_SCHEMA_VERSION",
    "StageBuildKeys",
    "derive_stage_build_keys",
    "stage_build_key",
]
