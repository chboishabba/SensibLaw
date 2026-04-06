import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.relation_graph import (
    build_provisional_invariant_readout,
    build_relation_similarity_summary,
    build_relation_graph,
    build_seed_relation_clusters,
    build_seed_relation_comparison,
    observation_signature,
    relational_signature,
    relational_similarity,
)
from src.ingestion.media_adapter import TextDocumentMediaAdapter, parse_canonical_text
from src.policy.legal_review_profile import build_legal_review_extract


def test_build_relation_graph_emits_actor_action_object_and_source_edges():
    graph = build_relation_graph(
        [
            {
                "text": "NSA reviewed surveillance authority after criticism.",
                "actor": "NSA",
                "action": "review",
                "object": "surveillance authority",
                "event_id": "ev:nsa:1",
                "source_id": "source:nsa:1",
            }
        ],
        graph_id="gwb:nsa",
    )

    assert graph.graph_id == "gwb:nsa"
    assert {node.node_kind for node in graph.nodes} == {"actor", "action", "object", "event", "source"}
    assert [edge.to_dict() for edge in graph.edges] == [
        {"source_id": "actor:NSA", "edge_kind": "acts_in", "target_id": "ev:nsa:1"},
        {"source_id": "ev:nsa:1", "edge_kind": "has_action", "target_id": "action:review"},
        {"source_id": "ev:nsa:1", "edge_kind": "acts_on", "target_id": "object:surveillance authority"},
        {"source_id": "ev:nsa:1", "edge_kind": "from_source", "target_id": "source:source:nsa:1"},
    ]


def test_relational_similarity_is_high_for_equivalent_candidate_skeletons():
    left = build_relation_graph(
        [
            {
                "text": "NSA reviewed surveillance authority after criticism.",
                "actor": "NSA",
                "action": "review",
                "object": "surveillance authority",
                "event_id": "ev:nsa:a",
                "source_id": "source:nsa:a",
            }
        ],
        graph_id="left",
    )
    right = build_relation_graph(
        [
            {
                "text": "Oversight process examined NSA surveillance after concern.",
                "actor": "NSA",
                "action": "review",
                "object": "surveillance authority",
                "event_id": "ev:nsa:b",
                "source_id": "source:nsa:b",
            }
        ],
        graph_id="right",
    )

    assert relational_signature(left) == {
        "actor_set": {"NSA"},
        "action_set": {"review"},
        "object_set": {"surveillance authority"},
        "edge_types": {"acts_in", "has_action", "acts_on", "from_source"},
        "edge_role_set": {
            "actor>acts_in>event",
            "event>acts_on>object",
            "event>from_source>source",
            "event>has_action>action",
        },
    }
    assert relational_similarity(left, right) == 1.0


def test_observation_signature_adds_provenance_and_workload_signals():
    signature = observation_signature(
        [
            {
                "text": "gwb_us_law:iraq_2002_authorization in checked_handoff",
                "source_row_id": "gwb_us_law:iraq_2002_authorization:checked_handoff",
                "source_family": "checked_handoff",
                "primary_workload_class": "support_breadth_gap",
                "workload_classes": ["support_breadth_gap"],
                "candidate_anchors": [
                    {
                        "anchor_kind": "support_kind",
                        "anchor_label": "broad_cue",
                        "anchor_value": "broad_cue",
                    }
                ],
            }
        ]
    )

    assert signature["source_family_set"] == {"checked_handoff"}
    assert signature["workload_class_set"] == {"support_breadth_gap"}
    assert signature["support_kind_set"] == {"broad_cue"}


def test_build_relation_graph_uses_legal_review_text_refs_when_no_explicit_source_id():
    adapter = TextDocumentMediaAdapter(source_artifact_ref="legal-review-graph")
    canonical = adapter.adapt("4 The board must consider section 15 before acting.")
    parsed_envelope = parse_canonical_text(canonical, parse_profile="legal_review")
    extract = build_legal_review_extract(
        parsed_envelope,
        lane="gwb",
        family_id="gwb_legal_review",
        cohort_id="gwb_legal_review_v1",
        root_artifact_id="gwb_legal_review_v1",
        source_family="gwb_legal_review",
        source_kind="review_source_text",
    )

    graph = build_relation_graph(extract["review_claim_records"], graph_id="legal-review")

    assert graph.graph_id == "legal-review"
    assert any(node.node_kind == "event" for node in graph.nodes)
    assert any(node.node_kind == "source" and node.label == canonical.text_id for node in graph.nodes)
    assert any(edge.edge_kind == "from_source" for edge in graph.edges)


def test_build_relation_similarity_summary_reports_shared_and_distinct_features():
    summary = build_relation_similarity_summary(
        [
            {
                "text": "NSA reviewed surveillance authority after criticism.",
                "actor": "NSA",
                "action": "review",
                "object": "surveillance authority",
                "event_id": "ev:nsa:a",
                "source_id": "source:nsa:a",
            }
        ],
        [
            {
                "text": "NSA reviewed surveillance authority after criticism.",
                "actor": "NSA",
                "action": "review",
                "event_id": "ev:nsa:b",
                "source_id": "source:nsa:b",
            }
        ],
        left_id="candidate:left",
        right_id="candidate:right",
    )

    assert summary["provisional_readout"]["comparison_band"] == "partially_overlapping"
    assert summary["shared_features"]["actors"] == ["NSA"]
    assert summary["shared_features"]["actions"] == ["review"]
    assert summary["shared_features"]["objects"] == []
    assert summary["shared_features"]["source_families"] == []
    assert summary["shared_features"]["workload_classes"] == []
    assert summary["shared_features"]["support_kinds"] == []
    assert summary["distinct_features"]["left_only"]["objects"] == ["surveillance authority"]
    assert summary["distinct_features"]["right_only"]["objects"] == []
    assert summary["provisional_readout"]["information_level"] == "semantic_rich"


def test_build_seed_relation_comparison_uses_checked_in_gwb_seed_fixture():
    fixture_path = (
        ROOT
        / "tests"
        / "fixtures"
        / "zelph"
        / "gwb_broader_review_v1"
        / "gwb_broader_review_v1.json"
    )
    payload = json.loads(fixture_path.read_text())

    comparison = build_seed_relation_comparison(
        payload["source_review_rows"],
        seed_id="gwb_us_law:nsa_surveillance_review",
    )

    assert comparison["seed_id"] == "gwb_us_law:nsa_surveillance_review"
    assert [item["source_row_id"] for item in comparison["candidate_graphs"]] == [
        "gwb_us_law:nsa_surveillance_review:checked_handoff",
        "gwb_us_law:nsa_surveillance_review:corpus_book_timeline",
    ]
    assert comparison["pairwise_comparisons"] == [
        {
            "left_source_row_id": "gwb_us_law:nsa_surveillance_review:checked_handoff",
            "right_source_row_id": "gwb_us_law:nsa_surveillance_review:corpus_book_timeline",
            "left_source_family": "checked_handoff",
            "right_source_family": "corpus_book_timeline",
            "similarity": 1.0,
            "left_signature": {
                "actor_set": [],
                "action_set": [],
                "object_set": [],
                "edge_types": ["from_source"],
                "edge_role_set": ["event>from_source>source"],
                "source_family_set": ["checked_handoff"],
                "support_kind_set": ["direct"],
                "workload_class_set": ["support_breadth_gap"],
            },
            "right_signature": {
                "actor_set": [],
                "action_set": [],
                "object_set": [],
                "edge_types": ["from_source"],
                "edge_role_set": ["event>from_source>source"],
                "source_family_set": ["corpus_book_timeline"],
                "support_kind_set": ["direct"],
                "workload_class_set": ["support_breadth_gap"],
            },
            "provisional_readout": {
                "comparison_band": "near_equivalent",
                "information_level": "low_information",
            },
        }
    ]


def test_build_seed_relation_clusters_groups_near_equivalent_seed_rows():
    fixture_path = (
        ROOT
        / "tests"
        / "fixtures"
        / "zelph"
        / "gwb_broader_review_v1"
        / "gwb_broader_review_v1.json"
    )
    payload = json.loads(fixture_path.read_text())

    clustered = build_seed_relation_clusters(
        payload["source_review_rows"],
        seed_id="gwb_us_law:nsa_surveillance_review",
    )

    assert clustered["seed_id"] == "gwb_us_law:nsa_surveillance_review"
    assert clustered["candidate_count"] == 2
    assert clustered["pairwise_comparison_count"] == 1
    assert clustered["clusters"] == [
        {
            "cluster_id": "cluster:gwb_us_law:nsa_surveillance_review:01",
            "cluster_kind": "near_equivalent_cluster",
            "member_source_row_ids": [
                "gwb_us_law:nsa_surveillance_review:checked_handoff",
                "gwb_us_law:nsa_surveillance_review:corpus_book_timeline",
            ],
            "member_source_families": [
                "checked_handoff",
                "corpus_book_timeline",
            ],
            "provisional_readout": {
                "comparison_band": "near_equivalent",
                "information_level": "low_information",
            },
        }
    ]


def test_build_provisional_invariant_readout_emits_operator_only_seed_summary():
    fixture_path = (
        ROOT
        / "tests"
        / "fixtures"
        / "zelph"
        / "gwb_broader_review_v1"
        / "gwb_broader_review_v1.json"
    )
    payload = json.loads(fixture_path.read_text())

    readout = build_provisional_invariant_readout(
        payload["source_review_rows"],
        seed_id="gwb_us_law:nsa_surveillance_review",
    )

    assert readout["seed_id"] == "gwb_us_law:nsa_surveillance_review"
    assert readout["candidate_count"] == 2
    assert readout["pairwise_comparison_count"] == 1
    assert readout["provisional_invariants"] == [
        {
            "provisional_invariant_id": "invariant:gwb_us_law:nsa_surveillance_review:01",
            "seed_id": "gwb_us_law:nsa_surveillance_review",
            "member_source_row_ids": [
                "gwb_us_law:nsa_surveillance_review:checked_handoff",
                "gwb_us_law:nsa_surveillance_review:corpus_book_timeline",
            ],
            "member_source_families": [
                "checked_handoff",
                "corpus_book_timeline",
            ],
            "supporting_pairwise_count": 1,
            "average_similarity": 1.0,
            "status": "provisional_invariant",
            "provisional_readout": {
                "comparison_band": "near_equivalent",
                "information_level": "low_information",
            },
        }
    ]


def test_iraq_seed_relation_comparison_exposes_distinct_source_families():
    fixture_path = (
        ROOT
        / "tests"
        / "fixtures"
        / "zelph"
        / "gwb_broader_review_v1"
        / "gwb_broader_review_v1.json"
    )
    payload = json.loads(fixture_path.read_text())

    comparison = build_seed_relation_comparison(
        payload["source_review_rows"],
        seed_id="gwb_us_law:iraq_2002_authorization",
    )

    assert comparison["seed_id"] == "gwb_us_law:iraq_2002_authorization"
    assert len(comparison["candidate_graphs"]) == 3
    assert len(comparison["pairwise_comparisons"]) == 3
    families = {
        frozenset(
            (
                item["left_source_family"],
                item["right_source_family"],
            )
        )
        for item in comparison["pairwise_comparisons"]
    }
    assert families == {
        frozenset(("checked_handoff", "public_bios_timeline")),
        frozenset(("checked_handoff", "corpus_book_timeline")),
        frozenset(("public_bios_timeline", "corpus_book_timeline")),
    }
    assert {
        item["provisional_readout"]["information_level"]
        for item in comparison["pairwise_comparisons"]
    } == {"low_information"}
