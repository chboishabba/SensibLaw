"""Complete source-to-checkpoint tranche phase contract.

The contract is shared by GWB, AU and Brexit. Profiles may supply different
source families and authority providers, but they cannot reorder the semantic
phases or let network enrichment block deterministic local compilation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.ontology.external_enrichment import canonical_sha256


TRANCHE_PIPELINE_CONTRACT = "complete-tranche-pipeline:v0_1"


class TranchePhase(IntEnum):
    SOURCE_INVENTORY = 10
    SOURCE_ACQUISITION = 20
    CANONICAL_PROJECTION = 30
    LOCAL_PNF_COMPILATION = 40
    LOCAL_WORLD_PROJECTION = 50
    EXTERNAL_DEMAND_PLANNING = 60
    EXTERNAL_ACQUISITION = 70
    TYPED_RECONCILIATION = 80
    REVIEW_PACKET = 90
    CHECKPOINT = 100

    @property
    def phase_ref(self) -> str:
        return f"tranche-phase:{self.name.lower()}:v0_1"


_PHASE_DEPENDENCIES: Mapping[TranchePhase, tuple[TranchePhase, ...]] = {
    TranchePhase.SOURCE_INVENTORY: (),
    TranchePhase.SOURCE_ACQUISITION: (TranchePhase.SOURCE_INVENTORY,),
    TranchePhase.CANONICAL_PROJECTION: (
        TranchePhase.SOURCE_INVENTORY,
        TranchePhase.SOURCE_ACQUISITION,
    ),
    TranchePhase.LOCAL_PNF_COMPILATION: (TranchePhase.CANONICAL_PROJECTION,),
    TranchePhase.LOCAL_WORLD_PROJECTION: (TranchePhase.LOCAL_PNF_COMPILATION,),
    TranchePhase.EXTERNAL_DEMAND_PLANNING: (
        TranchePhase.LOCAL_PNF_COMPILATION,
        TranchePhase.LOCAL_WORLD_PROJECTION,
    ),
    TranchePhase.EXTERNAL_ACQUISITION: (TranchePhase.EXTERNAL_DEMAND_PLANNING,),
    TranchePhase.TYPED_RECONCILIATION: (TranchePhase.EXTERNAL_ACQUISITION,),
    TranchePhase.REVIEW_PACKET: (TranchePhase.TYPED_RECONCILIATION,),
    TranchePhase.CHECKPOINT: (TranchePhase.REVIEW_PACKET,),
}


@dataclass(frozen=True)
class SourceFamily:
    family_ref: str
    path: str | None
    source_kind: str
    authority_class: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrancheProfile:
    profile_ref: str
    tranche: str
    jurisdiction: str
    source_families: tuple[SourceFamily, ...]
    legal_follow_profile: str | None
    local_projection_adapters: tuple[str, ...]
    provider_refs: tuple[str, ...] = ("wikidata", "wiktionary")
    authority_priority: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "source_families": [row.to_dict() for row in self.source_families],
        }


@dataclass(frozen=True)
class PhaseReceipt:
    phase: TranchePhase
    state: str
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    detail: Mapping[str, Any]

    @property
    def receipt_ref(self) -> str:
        return "tranche-phase-receipt:" + canonical_sha256(
            {
                "contract": TRANCHE_PIPELINE_CONTRACT,
                "phase_ref": self.phase.phase_ref,
                "state": self.state,
                "input_refs": list(self.input_refs),
                "output_refs": list(self.output_refs),
                "detail": dict(self.detail),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_ref": self.receipt_ref,
            "phase_ref": self.phase.phase_ref,
            "state": self.state,
            "input_refs": list(self.input_refs),
            "output_refs": list(self.output_refs),
            "detail": dict(self.detail),
            "authority": "execution_receipt_only",
        }


GWB_PROFILE = TrancheProfile(
    profile_ref="tranche-profile:gwb:v0_1",
    tranche="GWB",
    jurisdiction="US",
    source_families=(
        SourceFamily(
            "source-family:gwb-public-bios:v1",
            "demo/ingest/gwb/public_bios_v1/raw",
            "public_biography_html",
            "secondary_or_official_biographical",
        ),
        SourceFamily(
            "source-family:gwb-books:v1",
            "demo/ingest/gwb",
            "book_pdf_epub",
            "secondary_and_first_person_sources",
        ),
    ),
    legal_follow_profile="US",
    local_projection_adapters=(
        "projection:generic-pnf-world:v0_1",
        "projection:gwb-broader-corpus-braid:v1",
    ),
    authority_priority=(
        "official_us_legal_sources",
        "source_documents",
        "wikidata_structural_index",
    ),
)

AU_PROFILE = TrancheProfile(
    profile_ref="tranche-profile:au-legal:v0_1",
    tranche="AU",
    jurisdiction="AU",
    source_families=(
        SourceFamily(
            "source-family:au-legal-principles:v1",
            "demo/ingest/legal_principles_au_v1",
            "legal_material",
            "mixed_primary_and_secondary_legal",
        ),
        SourceFamily(
            "source-family:hca-s942025:v1",
            "demo/ingest/hca_case_s942025",
            "case_record_and_transcript",
            "primary_legal_record",
        ),
    ),
    legal_follow_profile="AU",
    local_projection_adapters=(
        "projection:generic-pnf-world:v0_1",
        "projection:au-corpus-scorecard:v1",
    ),
    authority_priority=(
        "official_au_legal_sources",
        "case_record",
        "wikidata_structural_index",
    ),
)

BREXIT_PROFILE = TrancheProfile(
    profile_ref="tranche-profile:brexit-gb:v0_1",
    tranche="BREXIT",
    jurisdiction="GB",
    source_families=(
        SourceFamily(
            "source-family:brexit-followed-legal:v1",
            None,
            "followed_legislation_and_case_law",
            "primary_legal_record",
        ),
    ),
    legal_follow_profile="GB",
    local_projection_adapters=("projection:generic-pnf-world:v0_1",),
    authority_priority=(
        "official_gb_legal_sources",
        "official_eu_legal_sources",
        "wikidata_structural_index",
    ),
)

_PROFILES = {
    "GWB": GWB_PROFILE,
    "AU": AU_PROFILE,
    "BREXIT": BREXIT_PROFILE,
}


def profile_for_tranche(value: str) -> TrancheProfile:
    try:
        return _PROFILES[value.upper()]
    except KeyError as error:
        raise ValueError(f"unsupported tranche: {value}") from error


def ordered_phases(*, include_network: bool = True) -> tuple[TranchePhase, ...]:
    phases = tuple(TranchePhase)
    if include_network:
        return phases
    return tuple(
        phase
        for phase in phases
        if phase not in {TranchePhase.EXTERNAL_ACQUISITION, TranchePhase.TYPED_RECONCILIATION, TranchePhase.REVIEW_PACKET}
    )


def validate_phase_receipts(receipts: Sequence[PhaseReceipt]) -> None:
    seen: set[TranchePhase] = set()
    previous = 0
    for receipt in receipts:
        if int(receipt.phase) <= previous:
            raise ValueError("tranche phase receipts are not strictly ordered")
        missing = [row for row in _PHASE_DEPENDENCIES[receipt.phase] if row not in seen]
        if missing:
            raise ValueError(
                f"phase {receipt.phase.name} missing dependencies: "
                + ", ".join(row.name for row in missing)
            )
        seen.add(receipt.phase)
        previous = int(receipt.phase)


def inventory_profile(profile: TrancheProfile, *, repo_root: Path) -> dict[str, Any]:
    families: list[dict[str, Any]] = []
    for family in profile.source_families:
        path = repo_root / family.path if family.path else None
        exists = bool(path and path.exists())
        files = (
            sorted(str(row.relative_to(repo_root)) for row in path.rglob("*") if row.is_file())
            if path and path.exists()
            else []
        )
        families.append(
            {
                **family.to_dict(),
                "exists": exists,
                "file_count": len(files),
                "files": files,
                "requires_acquisition": family.path is None or not exists,
            }
        )
    return {
        "profile": profile.to_dict(),
        "source_families": families,
        "summary": {
            "declared_family_count": len(families),
            "available_family_count": sum(row["exists"] for row in families),
            "acquisition_required_count": sum(row["requires_acquisition"] for row in families),
        },
        "authority": "inventory_only",
    }


def checkpoint_payload(
    *,
    profile: TrancheProfile,
    receipts: Sequence[PhaseReceipt],
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    validate_phase_receipts(receipts)
    return {
        "schema_version": "sl.complete_tranche_checkpoint.v0_1",
        "contract_ref": TRANCHE_PIPELINE_CONTRACT,
        "profile": profile.to_dict(),
        "phase_receipts": [row.to_dict() for row in receipts],
        "artifacts": dict(artifacts),
        "authority_boundaries": {
            "source_mentions_preserved": True,
            "external_candidates_are_not_identity": True,
            "local_compilation_network_independent": True,
            "world_entity_promotion_performed": False,
            "review_required_for_identity_closure": True,
        },
    }


__all__ = [
    "AU_PROFILE",
    "BREXIT_PROFILE",
    "GWB_PROFILE",
    "PhaseReceipt",
    "SourceFamily",
    "TRANCHE_PIPELINE_CONTRACT",
    "TranchePhase",
    "TrancheProfile",
    "checkpoint_payload",
    "inventory_profile",
    "ordered_phases",
    "profile_for_tranche",
    "validate_phase_receipts",
]
