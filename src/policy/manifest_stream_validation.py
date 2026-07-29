"""Bounded cross-family validation for streamed compilation manifests.

The validator retains only canonical references and pending child references.  It
never reconstructs a document artifact.  Callers admit verified descriptor
batches in any order and require ``finalize`` before completed-build or
occurrence publication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from src.policy.algebra.revision_identity import factor_revision_ref


@dataclass(frozen=True)
class ManifestClosureReceipt:
    factor_revision_count: int
    refinement_count: int
    demand_count: int
    anchor_count: int
    candidate_set_count: int
    candidate_build_count: int
    candidate_link_count: int

    def to_dict(self) -> dict[str, int | str | bool]:
        return {
            "schema_version": "sl.manifest_parent_closure_receipt.v0_1",
            "factor_revision_count": self.factor_revision_count,
            "refinement_count": self.refinement_count,
            "demand_count": self.demand_count,
            "anchor_count": self.anchor_count,
            "candidate_set_count": self.candidate_set_count,
            "candidate_build_count": self.candidate_build_count,
            "candidate_link_count": self.candidate_link_count,
            "parent_closure_complete": True,
        }


@dataclass
class ManifestParentClosureValidator:
    """Validate parent closure without retaining artifact payloads."""

    factor_revisions_by_factor: dict[str, str] = field(default_factory=dict)
    factor_revision_refs: set[str] = field(default_factory=set)
    refinement_refs: set[str] = field(default_factory=set)
    demand_refs: set[str] = field(default_factory=set)
    meet_refs: set[str] = field(default_factory=set)
    candidate_set_refs: set[str] = field(default_factory=set)
    candidate_build_refs: set[str] = field(default_factory=set)
    _pending_factor_parents: list[tuple[str, str, str]] = field(default_factory=list)
    _pending_candidate_set_builds: list[tuple[str, str, str]] = field(default_factory=list)
    _pending_links: list[tuple[str, str, str]] = field(default_factory=list)
    refinement_count: int = 0
    demand_count: int = 0
    anchor_count: int = 0
    candidate_link_count: int = 0

    def admit_factors(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for row in rows:
            factor_ref = str(row.get("factor_ref") or "")
            if not factor_ref:
                raise ValueError("manifest factor is missing factor_ref")
            revision_ref = factor_revision_ref(row)
            previous = self.factor_revisions_by_factor.get(factor_ref)
            if previous is not None and previous != revision_ref:
                raise ValueError(
                    "manifest contains conflicting base revisions for factor "
                    f"{factor_ref!r}"
                )
            self.factor_revisions_by_factor[factor_ref] = revision_ref
            self.factor_revision_refs.add(revision_ref)

    def admit_refinements(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for row in rows:
            refinement_ref = str(row.get("refinement_ref") or "")
            if not refinement_ref or refinement_ref in self.refinement_refs:
                raise ValueError("manifest refinement identity is missing or duplicated")
            prior = row.get("prior_factor")
            resulting = row.get("resulting_factor")
            if not isinstance(prior, Mapping) or not isinstance(resulting, Mapping):
                raise ValueError(f"refinement {refinement_ref!r} lacks factor revisions")
            prior_revision = factor_revision_ref(prior)
            resulting_revision = factor_revision_ref(resulting)
            self._pending_factor_parents.append(
                ("resolution.refinement.prior", refinement_ref, prior_revision)
            )
            self.factor_revision_refs.add(resulting_revision)
            self.factor_revisions_by_factor[str(resulting["factor_ref"])] = resulting_revision
            self.refinement_refs.add(refinement_ref)
            self.refinement_count += 1
            self._admit_candidate_links("refinement", refinement_ref, row)

    def admit_demands(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for row in rows:
            demand_ref = str(row.get("demand_ref") or "")
            factor_ref = str(row.get("factor_ref") or "")
            if not demand_ref or demand_ref in self.demand_refs:
                raise ValueError("manifest demand identity is missing or duplicated")
            parent = str(row.get("factor_revision_ref") or "")
            if not parent and factor_ref:
                parent = self.factor_revisions_by_factor.get(factor_ref, "")
            self._pending_factor_parents.append(
                ("resolution.demand", demand_ref, parent)
            )
            self.demand_refs.add(demand_ref)
            self.demand_count += 1
            self._admit_candidate_links("demand", demand_ref, row)

    def admit_meets(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for row in rows:
            meet_ref = str(row.get("meet_ref") or row.get("typed_meet_ref") or "")
            if not meet_ref or meet_ref in self.meet_refs:
                raise ValueError("manifest meet identity is missing or duplicated")
            self.meet_refs.add(meet_ref)
            self._admit_candidate_links("meet", meet_ref, row)

    def admit_anchors(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for row in rows:
            factor_ref = str(row.get("factor_ref") or "")
            parent = str(row.get("factor_revision_ref") or "")
            if not parent and factor_ref:
                parent = self.factor_revisions_by_factor.get(factor_ref, "")
            self._pending_factor_parents.append(("pnf.factor_anchor", factor_ref, parent))
            self.anchor_count += 1

    def admit_candidate_sets(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for row in rows:
            set_ref = str(row.get("candidate_set_ref") or "")
            if not set_ref or set_ref in self.candidate_set_refs:
                raise ValueError("candidate-set identity is missing or duplicated")
            factor_ref = str(row.get("reference_factor_ref") or "")
            parent = str(row.get("reference_factor_revision_ref") or "")
            if not parent and factor_ref:
                parent = self.factor_revisions_by_factor.get(factor_ref, "")
            self._pending_factor_parents.append(
                ("resolution.binding_candidate_set", set_ref, parent)
            )
            build_ref = str(row.get("generator_build_ref") or "")
            if not build_ref:
                raise ValueError(f"candidate set {set_ref!r} lacks generator_build_ref")
            self._pending_candidate_set_builds.append((set_ref, build_ref, parent))
            self.candidate_set_refs.add(set_ref)

    def admit_candidate_builds(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for row in rows:
            build_ref = str(row.get("generator_build_ref") or "")
            set_ref = str(row.get("candidate_set_ref") or "")
            parent = str(row.get("reference_factor_revision_ref") or "")
            if not build_ref or build_ref in self.candidate_build_refs:
                raise ValueError("candidate-build identity is missing or duplicated")
            if not set_ref:
                raise ValueError(f"candidate build {build_ref!r} lacks candidate_set_ref")
            self._pending_factor_parents.append(
                ("execution.binding_candidate_set_build", build_ref, parent)
            )
            self._pending_links.append(("candidate_build", build_ref, set_ref))
            self.candidate_build_refs.add(build_ref)

    def _admit_candidate_links(
        self, kind: str, source_ref: str, row: Mapping[str, Any]
    ) -> None:
        for set_ref in row.get("candidate_set_refs") or ():
            self._pending_links.append((kind, source_ref, str(set_ref)))
            self.candidate_link_count += 1

    def finalize(self) -> ManifestClosureReceipt:
        missing_factor_parents = sorted(
            (kind, child_ref, parent_ref)
            for kind, child_ref, parent_ref in self._pending_factor_parents
            if not parent_ref or parent_ref not in self.factor_revision_refs
        )
        if missing_factor_parents:
            kind, child_ref, parent_ref = missing_factor_parents[0]
            raise ValueError(
                "streamed manifest parent closure failed: "
                f"child_table={kind} child_ref={child_ref!r} "
                f"missing_factor_revision_ref={parent_ref!r}"
            )

        missing_builds = sorted(
            (set_ref, build_ref)
            for set_ref, build_ref, _parent in self._pending_candidate_set_builds
            if build_ref not in self.candidate_build_refs
        )
        if missing_builds:
            set_ref, build_ref = missing_builds[0]
            raise ValueError(
                "candidate set has no verified build descriptor: "
                f"candidate_set_ref={set_ref!r} generator_build_ref={build_ref!r}"
            )

        missing_sets = sorted(
            (kind, source_ref, set_ref)
            for kind, source_ref, set_ref in self._pending_links
            if set_ref not in self.candidate_set_refs
        )
        if missing_sets:
            kind, source_ref, set_ref = missing_sets[0]
            raise ValueError(
                "candidate-set link references an unverified set: "
                f"link_kind={kind!r} source_ref={source_ref!r} "
                f"candidate_set_ref={set_ref!r}"
            )

        return ManifestClosureReceipt(
            factor_revision_count=len(self.factor_revision_refs),
            refinement_count=self.refinement_count,
            demand_count=self.demand_count,
            anchor_count=self.anchor_count,
            candidate_set_count=len(self.candidate_set_refs),
            candidate_build_count=len(self.candidate_build_refs),
            candidate_link_count=self.candidate_link_count,
        )


__all__ = ["ManifestClosureReceipt", "ManifestParentClosureValidator"]
