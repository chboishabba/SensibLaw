from src.ontology.wikimedia_world_walk import (
    EdgeCandidate,
    WorldWalkPolicy,
    build_publishable_bucket_manifest,
    walk_world,
)


def _fixture_candidates(node_id: str) -> list[EdgeCandidate]:
    fixtures = {
        "mabo": [
            EdgeCandidate("mabo", "native-title", "wikidata_ontology", "P527", 9),
            EdgeCandidate("mabo", "common-law", "wikipedia_navigation", "internal-link", 8),
            EdgeCandidate("mabo", "hca-1992", "source_reference", "citation", 10),
        ],
        "hca-1992": [
            EdgeCandidate("hca-1992", "terra-nullius", "pnf_semantic", "predicate-weld", 9),
        ],
        "terra-nullius": [
            EdgeCandidate("terra-nullius", "mabo", "wikipedia_navigation", "internal-link", 7),
        ],
    }
    return fixtures.get(node_id, [])


def test_world_walk_is_bounded_append_only_and_preserves_typed_cycle_receipt() -> None:
    result = walk_world(
        seed="mabo",
        policy=WorldWalkPolicy(hop_budget=3, selections_per_hop=1),
        expand=_fixture_candidates,
    )

    assert result.seed == "mabo"
    assert result.hop_budget == 3
    assert result.actual_hops == 3
    assert [receipt.edge_family for receipt in result.receipts] == [
        "source_reference",
        "pnf_semantic",
        "wikipedia_navigation",
    ]
    assert result.receipts[-1].target == "mabo"
    assert result.receipts[-1].cycle is True
    assert result.nodes == ("mabo", "hca-1992", "terra-nullius")
    assert result.semantic_promotion is False
    assert result.live_publication_performed is False


def test_publish_projection_is_candidate_only_and_excludes_browsing_history() -> None:
    result = walk_world(
        seed="mabo",
        policy=WorldWalkPolicy(hop_budget=2, selections_per_hop=1),
        expand=_fixture_candidates,
    )

    manifest = build_publishable_bucket_manifest(
        result,
        selected_node_ids={"mabo", "hca-1992"},
        parent_bucket_cids=("bafy-parent",),
        compiler_version="world-walk-v0_1",
    )

    assert manifest["schema_version"] == "sl.wikimedia_world_bucket.v0_1"
    assert manifest["candidate_only"] is True
    assert manifest["semantic_promotion"] is False
    assert manifest["live_ipfs_publication_performed"] is False
    assert manifest["selected_node_ids"] == ["hca-1992", "mabo"]
    assert manifest["parent_bucket_cids"] == ["bafy-parent"]
    assert "reading_trail" not in manifest
    assert "browsing_history" not in manifest
    assert manifest["content_digest"].startswith("sha256:")
