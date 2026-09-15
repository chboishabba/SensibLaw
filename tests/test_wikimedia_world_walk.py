from pathlib import Path

from src.ontology.wikidata import StatementBundle
from src.ontology.wikimedia_world_walk import (
    EdgeCandidate,
    WorldBucketProjection,
    WorldWalkPolicy,
    build_publishable_bucket_manifest,
    edge_candidates_from_wikidata_bundles,
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


def test_world_walk_runtime_has_no_json_or_regex_dependency() -> None:
    source = Path("src/ontology/wikimedia_world_walk.py").read_text(encoding="utf-8")
    assert "import json" not in source
    assert "import re" not in source
    assert "json.dumps" not in source
    assert "re.compile" not in source


def test_wikidata_statement_bundles_compile_to_typed_world_edges() -> None:
    bundles = [
        StatementBundle("Q1", "P31", "Q5", "normal", None, (), ()),
        StatementBundle("Q1", "P361", "http://www.wikidata.org/entity/Q2", "normal", None, (), ()),
        StatementBundle("Q1", "P50", "Q3", "normal", None, (), ()),
        StatementBundle("Q1", "P279", "not-a-qid", "normal", None, (), ()),
    ]

    default_edges = edge_candidates_from_wikidata_bundles(bundles)
    assert [(edge.relation, edge.target, edge.edge_family) for edge in default_edges] == [
        ("P31", "Q5", "wikidata_ontology"),
        ("P361", "Q2", "wikidata_ontology"),
    ]

    explicit_property_edges = edge_candidates_from_wikidata_bundles(
        bundles,
        property_filter=("P50",),
    )
    assert [(edge.relation, edge.target, edge.edge_family) for edge in explicit_property_edges] == [
        ("P50", "Q3", "wikidata_property"),
    ]


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


def test_publish_projection_is_typed_candidate_only_and_excludes_browsing_history() -> None:
    result = walk_world(
        seed="mabo",
        policy=WorldWalkPolicy(hop_budget=2, selections_per_hop=1),
        expand=_fixture_candidates,
    )

    projection = build_publishable_bucket_manifest(
        result,
        selected_node_ids={"mabo", "hca-1992"},
        parent_bucket_cids=("bafy-parent",),
        compiler_version="world-walk-v0_1",
    )

    assert isinstance(projection, WorldBucketProjection)
    assert projection.schema_version == "sl.wikimedia_world_bucket.v0_1"
    assert projection.candidate_only is True
    assert projection.semantic_promotion is False
    assert projection.live_ipfs_publication_performed is False
    assert projection.publication_projection_is_browsing_history is False
    assert projection.selected_node_ids == ("hca-1992", "mabo")
    assert projection.parent_bucket_cids == ("bafy-parent",)
    assert projection.content_digest.startswith("sha256:")
    assert projection.packaging_target == "kant-erdfa-shardset"
    assert projection.manifest_format == "cbor-compatible-logical-envelope"
    assert projection.content_addressing == "sha256-now-cid-later"
    assert projection.sink_refs == ()
    assert projection.logical_shard_id.startswith("world-bucket:")


def test_projection_digest_is_deterministic_over_typed_fields() -> None:
    result = walk_world(
        seed="mabo",
        policy=WorldWalkPolicy(hop_budget=2, selections_per_hop=1),
        expand=_fixture_candidates,
    )
    first = build_publishable_bucket_manifest(
        result,
        selected_node_ids={"mabo", "hca-1992"},
        parent_bucket_cids=("bafy-parent",),
        compiler_version="world-walk-v0_1",
    )
    second = build_publishable_bucket_manifest(
        result,
        selected_node_ids={"hca-1992", "mabo"},
        parent_bucket_cids=("bafy-parent", "bafy-parent"),
        compiler_version="world-walk-v0_1",
    )
    assert first.content_digest == second.content_digest
    assert first.logical_shard_id == second.logical_shard_id
