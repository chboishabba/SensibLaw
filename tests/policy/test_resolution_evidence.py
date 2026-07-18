from src.policy.resolution_evidence import (
    EvidenceRole,
    adapt_wikidata_snapshot,
    adapt_worldmonitor_snapshot,
    assess_entity_resolution,
    assess_event_resolution,
    assess_readiness,
    build_document_local_evidence,
    refine_partial_pnf_factor,
)
from src.policy.resolution_proofs import (
    run_au_resolution_proof,
    run_gwb_resolution_proof,
)
from src.policy.resolution_store import ResolutionArtifactStore


def test_document_local_backend_preserves_multiple_evidence_rows():
    rows = build_document_local_evidence(
        demand={
            "demand_ref": "d1",
            "mention_ref": "m1",
            "subject_ref": "s1",
        },
        mentions=[
            {
                "mention_ref": "m1",
                "document_ref": "doc",
                "canonical_surface": "Bush",
            }
        ],
        coreference_clusters=[
            {
                "cluster_ref": "c1",
                "document_ref": "doc",
                "mention_refs": ["m1", "m2"],
            }
        ],
        local_types=[
            {
                "type_ref": "t1",
                "mention_ref": "m1",
                "local_type": "person",
                "provenance_refs": ["p1"],
            }
        ],
    )
    assert len(rows) == 2
    assert {row.evidence_role for row in rows} == {
        EvidenceRole.DOCUMENT_LOCAL_CLUSTER,
        EvidenceRole.ENTITY,
    }


def test_wikidata_adapter_requires_exact_revision():
    try:
        adapt_wikidata_snapshot(
            subject_ref="s",
            entity={"id": "Q1", "revision": "2"},
            requested_revision="1",
            provenance_refs=("p",),
        )
    except ValueError as error:
        assert "revision" in str(error)
    else:
        raise AssertionError("revision mismatch should fail")


def test_worldmonitor_preserves_observation_role():
    row = adapt_worldmonitor_snapshot(
        subject_ref="e",
        record={"id": "wm1", "title": "quake", "category": "earthquake"},
        record_role=EvidenceRole.OBSERVATION,
        snapshot_version="v1",
        provenance_refs=("p",),
    ).to_dict()
    assert row["evidence_role"] == "observation"


def test_entity_resolution_is_coordinate_based_not_ranked():
    snapshot = adapt_wikidata_snapshot(
        subject_ref="s",
        entity={
            "id": "Q1",
            "revision": "1",
            "labels": {"en": {"value": "Bush"}},
            "properties": {"P31": [{"entity_ref": "person"}]},
        },
        requested_revision="1",
        provenance_refs=("p",),
    ).to_dict()
    assessment = assess_entity_resolution(
        subject_ref="s",
        local={
            "local_ref": "l",
            "labels": ["Bush"],
            "type_refs": ["person"],
        },
        snapshot=snapshot,
    ).to_dict()
    assert assessment["outcome"] == "resolved"
    assert "score" not in assessment


def test_event_assessment_retains_all_typed_coordinates():
    snapshot = adapt_worldmonitor_snapshot(
        subject_ref="e",
        record={
            "id": "wm",
            "title": "September 11 attacks",
            "event_type": "attack",
            "date": "2001-09-11",
            "country": "US",
            "participants": {"affected": ["US"]},
            "source_name": "source",
        },
        record_role="occurrence",
        snapshot_version="v1",
        provenance_refs=("p",),
    ).to_dict()
    assessment = assess_event_resolution(
        subject_ref="e",
        local={
            "local_ref": "local",
            "labels": ["September 11 attacks"],
            "type_refs": ["attack"],
            "temporal": {"occurred_on": "2001-09-11"},
            "spatial": {"country": "US"},
            "participants": {"affected": ["US"]},
        },
        snapshot=snapshot,
    ).to_dict()
    assert {row["coordinate"] for row in assessment["coordinates"]} == {
        "event_type",
        "temporal",
        "spatial",
        "participants",
        "form",
        "lineage",
        "observation_occurrence",
    }


def test_refinement_changes_only_named_factor():
    pnf = {
        "partial_pnf_ref": "p",
        "slots": [
            {
                "slot_ref": "subject",
                "alternatives": ["local"],
                "residual_refs": ["external_identity_unresolved"],
            },
            {
                "slot_ref": "object",
                "alternatives": ["unchanged"],
                "residual_refs": [],
            },
        ],
    }
    assessment = {
        "assessment_ref": "a",
        "right_ref": "snap",
        "outcome": "resolved",
        "selected_identity_ref": "Q1",
    }
    refined, receipt = refine_partial_pnf_factor(
        partial_pnf=pnf,
        slot_ref="subject",
        assessments=(assessment,),
    )
    assert refined["slots"][1] == pnf["slots"][1]
    assert (
        receipt.to_dict()["unchanged_factor_witness"][
            "all_other_slots_unchanged"
        ]
        is True
    )


def test_readiness_never_has_editing_authority():
    row = assess_readiness(
        subject_ref="s",
        partial_pnf={"slots": []},
        assessments=({"assessment_ref": "a", "outcome": "resolved"},),
    ).to_dict()
    assert row["outcome"] == "promote"
    assert row["editing_authority"] is False


def test_gwb_and_au_proofs_preserve_distinct_outcomes():
    gwb = run_gwb_resolution_proof()
    au = run_au_resolution_proof()
    assert gwb["readiness"]["outcome"] == "hold"
    assert au["readiness"]["outcome"] == "promote"
    assert au["shared_semantics_only"] is True


def test_append_only_store_rejects_overwrite():
    store = ResolutionArtifactStore()
    try:
        digest = store.append("assessment", "a1", {"x": 1})
        assert store.append("assessment", "a1", {"x": 1}) == digest
        assert store.get("a1") == {"x": 1}
        assert store.count("assessment") == 1
        try:
            store.append("assessment", "a1", {"x": 2})
        except ValueError:
            pass
        else:
            raise AssertionError("append-only overwrite should fail")
    finally:
        store.close()
