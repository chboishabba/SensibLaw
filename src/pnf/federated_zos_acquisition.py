"""Federated acquisition policy over ZOS identity and eRDFa publication metadata.

This module is deliberately a routing/policy layer, not another semantic
compiler.  It decides whether a consumer residual may use local or remote
storage, parse-compute, discovery, or public-ontology candidate producers.
CanonicalSyncIdentity remains the object identity authority; publication and
federation never create claim truth, source authority, or PNF promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from src.pnf.lee_residual_search_gate import lee_search_decision_for_residual
from src.pnf.legal_semantic_export import LegalSemanticArtifactExport


FEDERATED_ZOS_ACQUISITION_CONTRACT = "sl.federated_zos_acquisition.v0_1"


class CorpusPrivacy(str, Enum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    LOCAL_ONLY = "local_only"


class SourceClass(str, Enum):
    PRIMARY_AUTHORITY = "primary_authority"
    SECONDARY_SOURCE = "secondary_source"
    MEASUREMENT_SOURCE = "measurement_source"
    COMPARATOR_SOURCE = "comparator_source"
    PUBLIC_ONTOLOGY = "public_ontology"


class FederatedCapability(str, Enum):
    STORAGE_MIRROR = "storage_mirror"
    PARSE_COMPUTE = "parse_compute"
    ROUTING_DISCOVERY = "routing_discovery"
    ONTOLOGY_CANDIDATES = "ontology_candidates"
    LEGAL_AUTHORITY_PROVIDER = "legal_authority_provider"


class RemoteCapability(str, Enum):
    STORAGE = "storage"
    COMPUTE = "compute"
    DISCOVERY = "discovery"
    ONTOLOGY = "ontology"


_CAPABILITY_FOR_REMOTE = {
    RemoteCapability.STORAGE: FederatedCapability.STORAGE_MIRROR,
    RemoteCapability.COMPUTE: FederatedCapability.PARSE_COMPUTE,
    RemoteCapability.DISCOVERY: FederatedCapability.ROUTING_DISCOVERY,
    RemoteCapability.ONTOLOGY: FederatedCapability.ONTOLOGY_CANDIDATES,
}


@dataclass(frozen=True, slots=True)
class AcquisitionPolicy:
    consumer_ref: str
    corpus_ref: str
    privacy: CorpusPrivacy
    allowed_source_classes: frozenset[SourceClass]
    allow_remote_storage: bool
    allow_remote_compute: bool
    allow_remote_discovery: bool
    allow_public_ontology_candidates: bool
    advertise_private_corpus: bool
    max_depth: int
    network_budget: int
    storage_budget_bytes: int

    @classmethod
    def legal_strict(cls, *, corpus_ref: str) -> "AcquisitionPolicy":
        return cls(
            consumer_ref="legal-proof-graph",
            corpus_ref=corpus_ref,
            privacy=CorpusPrivacy.RESTRICTED,
            allowed_source_classes=frozenset(
                {
                    SourceClass.PRIMARY_AUTHORITY,
                    SourceClass.SECONDARY_SOURCE,
                    SourceClass.PUBLIC_ONTOLOGY,
                }
            ),
            allow_remote_storage=False,
            allow_remote_compute=False,
            allow_remote_discovery=True,
            allow_public_ontology_candidates=True,
            advertise_private_corpus=False,
            max_depth=4,
            network_budget=64,
            storage_budget_bytes=512 * 1024 * 1024,
        )

    @classmethod
    def public_research(cls, *, corpus_ref: str) -> "AcquisitionPolicy":
        return cls(
            consumer_ref="public-research",
            corpus_ref=corpus_ref,
            privacy=CorpusPrivacy.PUBLIC,
            allowed_source_classes=frozenset(SourceClass),
            allow_remote_storage=True,
            allow_remote_compute=True,
            allow_remote_discovery=True,
            allow_public_ontology_candidates=True,
            advertise_private_corpus=False,
            max_depth=8,
            network_budget=1024,
            storage_budget_bytes=16 * 1024 * 1024 * 1024,
        )

    @classmethod
    def obsidian_local(cls, *, corpus_ref: str) -> "AcquisitionPolicy":
        return cls(
            consumer_ref="obsidian-linking",
            corpus_ref=corpus_ref,
            privacy=CorpusPrivacy.LOCAL_ONLY,
            allowed_source_classes=frozenset(
                {SourceClass.PUBLIC_ONTOLOGY, SourceClass.SECONDARY_SOURCE}
            ),
            allow_remote_storage=False,
            allow_remote_compute=False,
            allow_remote_discovery=True,
            allow_public_ontology_candidates=True,
            advertise_private_corpus=False,
            max_depth=2,
            network_budget=16,
            storage_budget_bytes=64 * 1024 * 1024,
        )


@dataclass(frozen=True, slots=True)
class FederatedPeer:
    peer_ref: str
    capabilities: frozenset[FederatedCapability]
    public_only: bool


@dataclass(frozen=True, slots=True)
class PeerAssignment:
    peer_ref: str
    capability: RemoteCapability
    receives_corpus_content: bool
    receives_private_corpus_identity: bool = False
    semantic_authority: bool = False


@dataclass(frozen=True, slots=True)
class PublicOntologyPeer:
    provider_ref: str
    source_class: SourceClass
    candidate_only: bool = True
    semantic_authority: bool = False
    ontology_transplant_allowed: bool = False

    def __post_init__(self) -> None:
        if self.source_class is not SourceClass.PUBLIC_ONTOLOGY:
            raise ValueError("public ontology peer must use PUBLIC_ONTOLOGY source class")


@dataclass(frozen=True, slots=True)
class FederatedContentObject:
    object_id: str
    content_digest: str
    locators: tuple[str, ...]
    content_identity_paid: bool
    semantic_authority: bool = False
    claim_truth_promoted: bool = False


@dataclass(frozen=True, slots=True)
class FederatedAcquisitionRequest:
    request_ref: str
    coordinate_ref: str
    source_class: SourceClass
    reason: str
    candidate_only: bool = True
    creates_fact: bool = False
    promotes_truth: bool = False


@dataclass(frozen=True, slots=True)
class FederatedAcquisitionPlan:
    coordinate_ref: str
    residual_level: str
    evidence_search_authorised: bool
    requests: tuple[FederatedAcquisitionRequest, ...]
    world_truth_claimed: bool = False
    party_admission_claimed: bool = False


def object_from_semantic_export(
    export: LegalSemanticArtifactExport,
) -> FederatedContentObject:
    """Project an existing ZOS sync identity into federation without promotion."""

    identity = export.sync_identity
    return FederatedContentObject(
        object_id=identity.object_id,
        content_digest=identity.content_digest,
        locators=tuple(identity.producer_locator_set),
        content_identity_paid=True,
    )


def _remote_allowed(policy: AcquisitionPolicy, capability: RemoteCapability) -> bool:
    if capability is RemoteCapability.STORAGE:
        return policy.allow_remote_storage
    if capability is RemoteCapability.COMPUTE:
        return policy.allow_remote_compute
    if capability is RemoteCapability.DISCOVERY:
        return policy.allow_remote_discovery
    return policy.allow_public_ontology_candidates


def choose_federated_peers(
    policy: AcquisitionPolicy,
    peers: Iterable[FederatedPeer],
    required: RemoteCapability,
) -> tuple[PeerAssignment, ...]:
    """Choose capability-compatible peers without leaking restricted corpus bytes.

    Discovery and ontology peers receive only a residual/source-class query.
    Corpus bytes are remote-visible only for public corpora when remote storage
    or compute is explicitly enabled.
    """

    if not _remote_allowed(policy, required):
        return ()
    capability = _CAPABILITY_FOR_REMOTE[required]
    rows: list[PeerAssignment] = []
    for peer in peers:
        if capability not in peer.capabilities:
            continue
        if policy.privacy is not CorpusPrivacy.PUBLIC and required in {
            RemoteCapability.STORAGE,
            RemoteCapability.COMPUTE,
        }:
            continue
        receives_content = (
            policy.privacy is CorpusPrivacy.PUBLIC
            and required in {RemoteCapability.STORAGE, RemoteCapability.COMPUTE}
        )
        rows.append(
            PeerAssignment(
                peer_ref=peer.peer_ref,
                capability=required,
                receives_corpus_content=receives_content,
                receives_private_corpus_identity=False,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.peer_ref))


def federated_plan_for_lee_residual(
    *,
    residual: dict[str, object],
    policy: AcquisitionPolicy,
    coordinate_ref: str,
) -> FederatedAcquisitionPlan:
    """Weld Lee/Mabo residual gating to federation without inventing facts."""

    decision = lee_search_decision_for_residual(residual)
    if not decision.evidence_search_authorised:
        return FederatedAcquisitionPlan(
            coordinate_ref=coordinate_ref,
            residual_level=decision.residual_level,
            evidence_search_authorised=False,
            requests=(),
        )

    if SourceClass.PRIMARY_AUTHORITY not in policy.allowed_source_classes:
        requests: tuple[FederatedAcquisitionRequest, ...] = ()
    else:
        requests = (
            FederatedAcquisitionRequest(
                request_ref=f"federated-search:{coordinate_ref}:primary-authority",
                coordinate_ref=coordinate_ref,
                source_class=SourceClass.PRIMARY_AUTHORITY,
                reason=decision.search_reason,
            ),
        )
    return FederatedAcquisitionPlan(
        coordinate_ref=coordinate_ref,
        residual_level=decision.residual_level,
        evidence_search_authorised=bool(requests),
        requests=requests,
    )


__all__ = [
    "FEDERATED_ZOS_ACQUISITION_CONTRACT",
    "AcquisitionPolicy",
    "CorpusPrivacy",
    "FederatedAcquisitionPlan",
    "FederatedAcquisitionRequest",
    "FederatedCapability",
    "FederatedContentObject",
    "FederatedPeer",
    "PeerAssignment",
    "PublicOntologyPeer",
    "RemoteCapability",
    "SourceClass",
    "choose_federated_peers",
    "federated_plan_for_lee_residual",
    "object_from_semantic_export",
]
