from __future__ import annotations

from src.pnf.federated_zos_acquisition import (
    AcquisitionPolicy,
    CorpusPrivacy,
    FederatedCapability,
    FederatedPeer,
    PublicOntologyPeer,
    RemoteCapability,
    SourceClass,
    choose_federated_peers,
    federated_plan_for_lee_residual,
    object_from_semantic_export,
)
from src.pnf.legal_semantic_export import export_legal_semantic_build


def test_ipfs_and_erdfa_are_transport_identity_not_semantic_authority() -> None:
    build = {"build": {"build_ref": "legal-semantic-build:mabo"}}
    export = export_legal_semantic_build(
        build,
        locators=("ipfs://bafy-mabo", "https://mirror.example/mabo"),
    )
    obj = object_from_semantic_export(export)

    assert obj.object_id == "legal-semantic-build:mabo"
    assert obj.content_digest.startswith("sha256:")
    assert "ipfs://bafy-mabo" in obj.locators
    assert obj.content_identity_paid is True
    assert obj.semantic_authority is False
    assert obj.claim_truth_promoted is False


def test_restricted_legal_policy_does_not_disclose_private_corpus_to_federation() -> None:
    policy = AcquisitionPolicy.legal_strict(corpus_ref="matter:private:mabo")
    storage_peer = FederatedPeer(
        peer_ref="peer:archive",
        capabilities=frozenset({FederatedCapability.STORAGE_MIRROR}),
        public_only=False,
    )
    router_peer = FederatedPeer(
        peer_ref="peer:router",
        capabilities=frozenset({FederatedCapability.ROUTING_DISCOVERY}),
        public_only=True,
    )

    chosen = choose_federated_peers(
        policy,
        (storage_peer, router_peer),
        required=RemoteCapability.DISCOVERY,
    )

    assert policy.privacy is CorpusPrivacy.RESTRICTED
    assert policy.advertise_private_corpus is False
    assert [row.peer_ref for row in chosen] == ["peer:router"]
    assert all(row.receives_corpus_content is False for row in chosen)


def test_capability_specialisation_allows_storage_compute_and_routing_to_be_separate() -> None:
    policy = AcquisitionPolicy.public_research(corpus_ref="public:mabo")
    peers = (
        FederatedPeer("peer:store", frozenset({FederatedCapability.STORAGE_MIRROR}), True),
        FederatedPeer("peer:compute", frozenset({FederatedCapability.PARSE_COMPUTE}), True),
        FederatedPeer("peer:route", frozenset({FederatedCapability.ROUTING_DISCOVERY}), True),
    )

    assert [row.peer_ref for row in choose_federated_peers(policy, peers, RemoteCapability.STORAGE)] == ["peer:store"]
    assert [row.peer_ref for row in choose_federated_peers(policy, peers, RemoteCapability.COMPUTE)] == ["peer:compute"]
    assert [row.peer_ref for row in choose_federated_peers(policy, peers, RemoteCapability.DISCOVERY)] == ["peer:route"]


def test_public_ontology_peers_are_parallel_candidate_producers_not_truth_authorities() -> None:
    peers = (
        PublicOntologyPeer("wikidata", SourceClass.PUBLIC_ONTOLOGY),
        PublicOntologyPeer("dbpedia", SourceClass.PUBLIC_ONTOLOGY),
        PublicOntologyPeer("medical-ontology", SourceClass.PUBLIC_ONTOLOGY),
        PublicOntologyPeer("oeis", SourceClass.PUBLIC_ONTOLOGY),
    )

    assert {row.provider_ref for row in peers} == {"wikidata", "dbpedia", "medical-ontology", "oeis"}
    assert all(row.candidate_only for row in peers)
    assert all(not row.semantic_authority for row in peers)
    assert all(not row.ontology_transplant_allowed for row in peers)


def test_mabo_exact_common_ground_generates_zero_federated_work() -> None:
    policy = AcquisitionPolicy.legal_strict(corpus_ref="matter:mabo")
    plan = federated_plan_for_lee_residual(
        residual={"level": "exact"},
        policy=policy,
        coordinate_ref="mabo:native-title",
    )

    assert plan.evidence_search_authorised is False
    assert plan.requests == ()
    assert plan.world_truth_claimed is False
    assert plan.party_admission_claimed is False


def test_live_mabo_residual_emits_bounded_primary_source_request_without_fact_creation() -> None:
    policy = AcquisitionPolicy.legal_strict(corpus_ref="matter:mabo")
    plan = federated_plan_for_lee_residual(
        residual={"level": "contradiction"},
        policy=policy,
        coordinate_ref="mabo:terra-nullius:authority",
    )

    assert plan.evidence_search_authorised is True
    assert len(plan.requests) == 1
    request = plan.requests[0]
    assert request.source_class is SourceClass.PRIMARY_AUTHORITY
    assert request.coordinate_ref == "mabo:terra-nullius:authority"
    assert request.candidate_only is True
    assert request.creates_fact is False
    assert request.promotes_truth is False
