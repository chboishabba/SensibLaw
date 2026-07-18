"""PNF as a graph of reusable factors and declared relations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from src.policy.algebra import Factor, FactorConstraint
from src.policy.carriers.canonical import canonical_refs, require_text


@dataclass(frozen=True)
class PNFGraph:
    graph_ref: str
    document_ref: str
    factors: tuple[Factor[Any], ...]
    constraints: tuple[FactorConstraint, ...] = ()
    relation_refs: tuple[str, ...] = ()
    residuals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        refs = [factor.factor_ref for factor in self.factors]
        if len(refs) != len(set(refs)):
            raise ValueError("PNF graph factors require unique references")

    def factor(self, factor_ref: str) -> Factor[Any]:
        for factor in self.factors:
            if factor.factor_ref == factor_ref:
                return factor
        raise KeyError(factor_ref)

    def replace_factor(self, factor: Factor[Any]) -> "PNFGraph":
        if factor.factor_ref not in {row.factor_ref for row in self.factors}:
            raise ValueError("cannot replace an unknown PNF factor")
        return replace(
            self,
            factors=tuple(
                factor if row.factor_ref == factor.factor_ref else row
                for row in self.factors
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "sl.pnf_graph.v0_1",
            "graph_ref": require_text(self.graph_ref, "graph_ref"),
            "document_ref": require_text(self.document_ref, "document_ref"),
            "factors": [
                row.to_dict()
                for row in sorted(self.factors, key=lambda value: value.factor_ref)
            ],
            "constraints": [
                row.to_dict()
                for row in sorted(
                    self.constraints, key=lambda value: value.constraint_ref
                )
            ],
            "relation_refs": list(canonical_refs(self.relation_refs)),
            "residuals": list(canonical_refs(self.residuals)),
            "authority": "candidate_only",
        }
