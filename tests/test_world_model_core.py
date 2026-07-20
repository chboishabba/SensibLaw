from __future__ import annotations

from src.policy.world_model import (
    CANDIDATE_WORLD_MODEL_SCHEMA_VERSION,
    build_relation_edge,
    build_state_node,
    build_world_model,
    normalize_world_model,
)
from src.policy.world_model_adapters import (
    ClaimStateRecordMapping,
    ReviewClaimRecordMapping,
    StateNodeMapping,
    build_claim_nodes_from_mapping,
    build_claim_state_records,
    build_review_claim_records,
)
from src.policy.world_model_projections import (
    WORLD_MODEL_PROJECTION_SCHEMA_VERSION,
    build_projection,
    project_claim_table,
    project_linkage_case,
    project_report,
    project_review_surface,
    project_timeline,
)
from src.policy.world_model_profiles import (
    WORLD_MODEL_PROFILE_SCHEMA_VERSION,
    build_profile,
    normalize_profile,
)


def test_build_world_model_keeps_typed_candidate_state() -> None:
    claim = build_state_node(
        node_id="claim:1",
        node_kind="claim",
        label="Candidate claim",
        status="candidate",
        source_anchor_ids=["source:1"],
        authority_surface="review_surface",
        promotion_status="review_only",
    )
    relation = build_relation_edge(
        relation_id="rel:1",
        source_id="claim:1",
        target_id="event:1",
        relation_kind="supports",
        status="coalesced",
        source_anchor_ids=["source:1"],
    )

    world_model = build_world_model(
        model_id="model:1",
        lane_family="demo_lane",
        claims=[claim],
        relations=[relation],
        summary={"claim_count": 1},
        metadata={"demo": True},
    )

    assert world_model["schema_version"] == CANDIDATE_WORLD_MODEL_SCHEMA_VERSION
    assert world_model["model_id"] == "model:1"
    assert world_model["lane_family"] == "demo_lane"
    assert world_model["claims"][0]["node_kind"] == "claim"
    assert world_model["relations"][0]["relation_kind"] == "supports"
    assert world_model["status_counts"] == {
        "candidate": 1,
        "coalesced": 1,
    }


def test_project_report_keeps_world_model_reference() -> None:
    world_model = build_world_model(
        model_id="model:2",
        lane_family="demo_lane",
        claims=[{"claim_id": "claim:2", "status": "REVIEW_ONLY"}],
        summary={"claim_count": 1},
    )
    report = project_report(
        world_model,
        schema_version="sl.demo_report.v0_1",
        artifact_id="artifact:2",
        lane_id="demo",
        family_id="demo_lane",
        summary={"claim_count": 1},
        extra_fields={"report_kind": "demo"},
    )

    assert report["schema_version"] == "sl.demo_report.v0_1"
    assert report["world_model_ref"]["model_id"] == "model:2"
    assert report["projection"]["schema_version"] == WORLD_MODEL_PROJECTION_SCHEMA_VERSION
    assert report["projection"]["projection_kind"] == "report"
    assert report["report_kind"] == "demo"


def test_normalize_world_model_rebinds_report_like_payload() -> None:
    normalized = normalize_world_model(
        {
            "artifact_id": "artifact:3",
            "lane_id": "demo_lane",
            "claims": [{"claim_id": "claim:3"}],
            "summary": {"claim_count": 1},
        }
    )

    assert normalized["model_id"] == "artifact:3"
    assert normalized["lane_family"] == "demo_lane"
    assert normalized["claims"][0]["claim_id"] == "claim:3"


def test_build_projection_wraps_payload_without_promotion() -> None:
    world_model = build_world_model(model_id="model:4", lane_family="demo_lane")
    projection = build_projection(
        projection_id="timeline:model:4",
        projection_kind="timeline",
        world_model=world_model,
        payload={"timeline_count": 0},
        summary={"empty": True},
    )

    assert projection["schema_version"] == WORLD_MODEL_PROJECTION_SCHEMA_VERSION
    assert projection["source_model"]["model_status"] == "candidate"
    assert projection["payload"]["timeline_count"] == 0


def test_projection_family_covers_claims_timeline_review_and_linkage_case() -> None:
    world_model = build_world_model(
        model_id="model:5",
        lane_family="demo_lane",
        claims=[{"claim_id": "claim:5", "status": "candidate"}],
        events=[{"event_id": "event:5", "status": "coalesced"}],
        timelines=[{"timeline_id": "timeline:5", "status": "coalesced"}],
        summary={"claim_count": 1},
    )

    claim_table = project_claim_table(world_model)
    timeline = project_timeline(world_model)
    review_surface = project_review_surface(world_model)
    linkage_case = project_linkage_case(
        world_model,
        case_id="case:5",
        nodes=[{"id": "source:1", "layer": "source_anchor", "label": "Source"}],
        edges=[],
        expected_anchor_ids=["source:1"],
        expected_terminal_ids=["tranche:1"],
    )

    assert claim_table["projection_kind"] == "claim_table"
    assert claim_table["payload"]["row_count"] == 1
    assert timeline["projection_kind"] == "timeline"
    assert timeline["payload"]["timeline_count"] == 1
    assert review_surface["projection_kind"] == "review_surface"
    assert review_surface["payload"]["review_row_count"] == 1
    assert linkage_case["projection_kind"] == "linkage_case"
    assert linkage_case["payload"]["case_id"] == "case:5"
    assert linkage_case["source_model"]["model_id"] == "model:5"


def test_world_model_profiles_stay_generic_and_normalized() -> None:
    profile = build_profile(
        profile_id="q43229_superclass_pressure",
        lane_family="nat",
        source_kinds=["review_bucket", "operator_packet"],
        authority_surfaces=["wd_community_review_surface", "workflow_tranche_anchor"],
        external_bridges=["wikidata"],
        default_projection_kinds=["report", "review_surface", "linkage_case"],
    )
    normalized = normalize_profile({"profile_id": "broader_review", "lane_family": "gwb"})

    assert profile["schema_version"] == WORLD_MODEL_PROFILE_SCHEMA_VERSION
    assert profile["profile_id"] == "q43229_superclass_pressure"
    assert profile["lane_family"] == "nat"
    assert normalized["profile_id"] == "broader_review"
    assert normalized["lane_family"] == "gwb"


def test_world_model_adapters_build_generic_claim_nodes_and_review_claim_records() -> None:
    claim_nodes = build_claim_nodes_from_mapping(
        [{"event_id": "ev1", "candidate_id": "cand1", "label": "Signed", "status": "coalesced"}],
        mapping=StateNodeMapping(
            node_id=lambda row, _context: f"relation:{row['event_id']}:{row['candidate_id']}",
            node_kind=lambda _row, _context: "relation_candidate",
            label="label",
            status="status",
            source_anchor_ids=lambda row, _context: [row["event_id"]],
            promotion_status=lambda _row, _context: "candidate_only",
        ),
    )
    review_claims = build_review_claim_records(
        [{"fact_id": "fact:1", "label": "Candidate fact"}],
        family_id="demo_family",
        context={"run_id": "run:1", "cohort_id": "cohort:1"},
        mapping=ReviewClaimRecordMapping(
            claim_id="fact_id",
            candidate_id="fact_id",
            cohort_id=lambda _row, context: context["cohort_id"],
            root_artifact_id=lambda _row, context: context["run_id"],
            source_family=lambda _row, _context: "demo_source",
            authority_level=lambda _row, _context: "review_bundle",
            claim_status=lambda _row, _context: "REVIEW_ONLY",
            evidence_status=lambda _row, _context: "review_only",
            source_property=lambda _row, _context: "demo_source_property",
            target_property=lambda _row, _context: "demo_target_property",
            state_basis=lambda _row, _context: "demo_state_basis",
            provenance_chain=lambda _row, context: {"run_id": context["run_id"]},
            canonical_form=lambda row, context: {
                "subject": row["fact_id"],
                "property": "demo_fact",
                "value": row["label"],
                "references": [],
                "window_id": context["run_id"],
            },
        ),
    )

    assert claim_nodes[0]["node_id"] == "relation:ev1:cand1"
    assert claim_nodes[0]["node_kind"] == "relation_candidate"
    assert review_claims[0]["claim_id"] == "fact:1"
    assert review_claims[0]["nat_claim"]["state_basis"] == "demo_state_basis"
    assert review_claims[0]["action_policy"]["actionability"] == "must_review"


def test_world_model_adapters_build_generic_claim_state_records() -> None:
    claim_states = build_claim_state_records(
        [{"doc_id": "doc:1", "title": "Archive title", "anchor_date": "2020-01-31"}],
        family_id="archive_lane",
        context={"lane_id": "archive_lane"},
        mapping=ClaimStateRecordMapping(
            claim_id="doc_id",
            candidate_id="doc_id",
            cohort_id=lambda _row, context: context["lane_id"],
            root_artifact_id="doc_id",
            run_id="anchor_date",
            source_unit_id=lambda row, _context: f"archive:{row['doc_id']}",
            source_family=lambda _row, _context: "archive_record",
            authority_level=lambda _row, _context: "archive_record",
            claim_status=lambda _row, _context: "REVIEW_ONLY",
            nat_claim_state=lambda _row, _context: "REVIEW_ONLY",
            evidence_status=lambda _row, _context: "single_run",
            source_property=lambda _row, _context: "archive_source",
            target_property=lambda _row, _context: "policy_intent",
            state_basis=lambda _row, _context: "archive_lane",
            provenance_chain=lambda row, context: {"doc_id": row["doc_id"], "lane_id": context["lane_id"]},
            canonical_form=lambda row, _context: {
                "subject": row["doc_id"],
                "property": "policy_intent",
                "value": row["title"],
                "window_id": row["anchor_date"],
            },
        ),
    )

    assert claim_states[0]["claim_id"] == "doc:1"
    assert claim_states[0]["nat_claim"]["state"] == "REVIEW_ONLY"
    assert claim_states[0]["evidence_paths"][0]["run_id"] == "2020-01-31"
    assert claim_states[0]["action_policy"]["actionability"] == "must_review"
