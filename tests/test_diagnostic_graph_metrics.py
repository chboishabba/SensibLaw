from __future__ import annotations

from src.policy.diagnostic_graph_metrics import (
    GRAPH_CONE_SCHEMA_VERSION,
    GRAPH_DIAGNOSTICS_SCHEMA_VERSION,
    GRAPH_REVISION_STABILITY_SCHEMA_VERSION,
    build_graph_cone_diagnostics,
    build_graph_diagnostics,
    build_graph_revision_stability,
)
from src.policy.suite_normalized_artifact import build_suite_graph_diagnostics


def test_build_graph_diagnostics_is_deterministic_and_isolated() -> None:
    graph_payload = {
        "version": "fixture.graph.v1",
        "nodes": [
            {"id": "seed:a", "kind": "seed_lane", "label": "Seed A"},
            {"id": "source:r1", "kind": "source_row", "label": "Source 1"},
            {"id": "followed:u1", "kind": "followed_source", "label": "URL 1"},
            {"id": "lonely:x", "kind": "source_family", "label": "Family X"},
        ],
        "edges": [
            {"source": "seed:a", "target": "source:r1", "kind": "supports_source_row", "metadata": {}},
            {"source": "source:r1", "target": "followed:u1", "kind": "follows_source", "metadata": {}},
        ],
    }

    left = build_graph_diagnostics(
        graph_payload=graph_payload,
        source_artifact_id="artifact:1",
        source_lane="gwb",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v1",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row", "follows_source"),
        cone_max_depth=2,
    )
    right = build_graph_diagnostics(
        graph_payload=graph_payload,
        source_artifact_id="artifact:1",
        source_lane="gwb",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v1",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row", "follows_source"),
        cone_max_depth=2,
    )

    assert left == right
    assert left["schema_version"] == GRAPH_DIAGNOSTICS_SCHEMA_VERSION
    assert left["metrics"] == {
        "node_count": 4,
        "edge_count": 2,
        "component_count": 2,
        "giant_component_ratio": 0.75,
        "branching_factor": 0.5,
    }
    assert "promotion_gate" not in left
    assert "gate_decision" not in left["metrics"]
    assert left["cone"]["schema_version"] == GRAPH_CONE_SCHEMA_VERSION
    assert left["cone"]["seed_set"] == ["seed:a"]
    assert left["cone"]["width_by_depth"] == {"0": 1, "1": 1, "2": 1}
    assert left["cone"]["selectivity"] == 1.0
    assert left["cone"]["leakage"] == 0.0


def test_build_graph_cone_diagnostics_rejects_invalid_depth() -> None:
    try:
        build_graph_cone_diagnostics(
            graph_payload={"nodes": [], "edges": []},
            seed_node_kinds=("seed_lane",),
            allowed_edge_types=("supports_source_row",),
            max_depth=-1,
        )
    except ValueError as exc:
        assert "max_depth" in str(exc)
    else:
        raise AssertionError("Expected ValueError for negative max_depth")


def test_build_graph_cone_diagnostics_tracks_disallowed_boundary_edges() -> None:
    graph_payload = {
        "nodes": [
            {"id": "seed:a", "kind": "seed_lane", "label": "Seed A"},
            {"id": "source:r1", "kind": "source_row", "label": "Source 1"},
            {"id": "followed:u1", "kind": "followed_source", "label": "URL 1"},
            {"id": "link:k1", "kind": "linkage_kind", "label": "Linkage"},
        ],
        "edges": [
            {"source": "seed:a", "target": "source:r1", "kind": "supports_source_row", "metadata": {}},
            {"source": "seed:a", "target": "link:k1", "kind": "uses_linkage_kind", "metadata": {}},
            {"source": "source:r1", "target": "followed:u1", "kind": "follows_source", "metadata": {}},
        ],
    }

    cone = build_graph_cone_diagnostics(
        graph_payload=graph_payload,
        seed_node_kinds=("seed_lane",),
        allowed_edge_types=("supports_source_row", "follows_source"),
        max_depth=2,
    )

    assert cone["width_by_depth"] == {"0": 1, "1": 1, "2": 1}
    assert cone["selectivity"] == 0.666667
    assert cone["leakage"] == 0.333333


def test_build_graph_revision_stability_is_deterministic_and_bounded() -> None:
    baseline = build_graph_diagnostics(
        graph_payload={
            "version": "fixture.graph.v1",
            "nodes": [
                {"id": "seed:a", "kind": "seed_lane"},
                {"id": "row:1", "kind": "source_row"},
                {"id": "follow:1", "kind": "followed_source"},
            ],
            "edges": [
                {"source": "seed:a", "target": "row:1", "kind": "supports_source_row"},
                {"source": "row:1", "target": "follow:1", "kind": "follows_source"},
            ],
        },
        source_artifact_id="artifact:baseline",
        source_lane="gwb",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v1",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row", "follows_source"),
        cone_max_depth=2,
    )
    candidate = build_graph_diagnostics(
        graph_payload={
            "version": "fixture.graph.v2",
            "nodes": [
                {"id": "seed:a", "kind": "seed_lane"},
                {"id": "row:1", "kind": "source_row"},
                {"id": "row:2", "kind": "source_row"},
                {"id": "link:1", "kind": "linkage_kind"},
            ],
            "edges": [
                {"source": "seed:a", "target": "row:1", "kind": "supports_source_row"},
                {"source": "seed:a", "target": "row:2", "kind": "supports_source_row"},
                {"source": "seed:a", "target": "link:1", "kind": "uses_linkage_kind"},
            ],
        },
        source_artifact_id="artifact:candidate",
        source_lane="gwb",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v2",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row", "follows_source"),
        cone_max_depth=2,
    )

    baseline_snapshot = {"baseline": baseline.copy(), "candidate": candidate.copy()}
    left = build_graph_revision_stability(
        baseline_diagnostics=baseline,
        candidate_diagnostics=candidate,
    )
    right = build_graph_revision_stability(
        baseline_diagnostics=baseline,
        candidate_diagnostics=candidate,
    )

    assert left == right
    assert left["schema_version"] == GRAPH_REVISION_STABILITY_SCHEMA_VERSION
    assert left["admissibility"]["admissible"] is True
    assert left["admissibility"]["seed_set_changed"] is False
    assert left["comparison_scope"]["comparison_basis"] == "explicit_graph_diagnostics_pair"
    assert left["deltas"] == {
        "node_count_delta": 1,
        "edge_count_delta": 1,
        "component_count_delta": 0,
        "giant_component_ratio_delta": 0.0,
        "branching_factor_delta": 0.083333,
        "depth_reached_delta": -1,
        "selectivity_delta": -0.333333,
        "leakage_delta": 0.333333,
        "seed_count_delta": 0,
        "width_delta_by_depth": {"0": 0, "1": 1, "2": -1},
    }
    assert "gate_decision" not in left["deltas"]
    assert "promotion_gate" not in left
    assert baseline == baseline_snapshot["baseline"]
    assert candidate == baseline_snapshot["candidate"]


def test_build_graph_revision_stability_fails_closed_on_scope_mismatch() -> None:
    baseline = build_graph_diagnostics(
        graph_payload={"nodes": [{"id": "seed:a", "kind": "seed_lane"}], "edges": []},
        source_artifact_id="artifact:baseline",
        source_lane="gwb",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v1",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row",),
        cone_max_depth=1,
    )
    candidate = build_graph_diagnostics(
        graph_payload={"nodes": [{"id": "seed:a", "kind": "seed_lane"}], "edges": []},
        source_artifact_id="artifact:candidate",
        source_lane="au",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v2",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row",),
        cone_max_depth=1,
    )

    stability = build_graph_revision_stability(
        baseline_diagnostics=baseline,
        candidate_diagnostics=candidate,
    )

    assert stability["admissibility"]["admissible"] is False
    assert stability["admissibility"]["same_source_lane"] is False
    assert stability["admissibility"]["rejection_reasons"] == ["source_lane_mismatch"]
    assert stability["deltas"] == {}


def test_build_suite_graph_diagnostics_omits_revision_stability_without_explicit_pair() -> None:
    diagnostics = build_suite_graph_diagnostics(
        graph_payload={
            "version": "fixture.graph.v1",
            "nodes": [{"id": "seed:a", "kind": "seed_lane"}],
            "edges": [],
        },
        source_artifact_id="artifact:current",
        source_lane="gwb",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v1",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row",),
        cone_max_depth=1,
    )

    assert diagnostics["schema_version"] == GRAPH_DIAGNOSTICS_SCHEMA_VERSION
    assert "revision_stability" not in diagnostics


def test_build_suite_graph_diagnostics_attaches_rejected_revision_stability_for_explicit_bad_pair() -> None:
    baseline = build_graph_diagnostics(
        graph_payload={
            "version": "fixture.graph.v1",
            "nodes": [{"id": "seed:a", "kind": "seed_lane"}],
            "edges": [],
        },
        source_artifact_id="artifact:baseline",
        source_lane="au",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v1",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row",),
        cone_max_depth=1,
    )

    diagnostics = build_suite_graph_diagnostics(
        graph_payload={
            "version": "fixture.graph.v2",
            "nodes": [{"id": "seed:a", "kind": "seed_lane"}],
            "edges": [],
        },
        source_artifact_id="artifact:candidate",
        source_lane="gwb",
        substrate_kind="legal_follow_graph",
        projection_role="suite_normalized_artifact",
        graph_version="fixture.graph.v2",
        cone_seed_node_kinds=("seed_lane",),
        cone_allowed_edge_types=("supports_source_row",),
        cone_max_depth=1,
        baseline_graph_diagnostics=baseline,
    )

    revision_stability = diagnostics["revision_stability"]
    assert revision_stability["schema_version"] == GRAPH_REVISION_STABILITY_SCHEMA_VERSION
    assert revision_stability["admissibility"]["admissible"] is False
    assert revision_stability["admissibility"]["rejection_reasons"] == ["source_lane_mismatch"]
    assert revision_stability["deltas"] == {}
