"""Source history joins to *real emitted* Wiki review consumers, not only IDs.

Deliberation evidence here is a synthetic *candidate assessment*. The reports
are the existing real fixture-backed climate/repair/P2738/hotspot lane builders.
"""
from copy import deepcopy

import pytest

from src.ontology.wikidata_lane_status import build_wikidata_lane_bundle
from src.ontology.wikidata_signal_review_bundle import attach_deliberation_context

HISTORY = {
    "version": "itir.governance.deliberation_assessment.v1",
    "packet_ref": "deliberation:sha256:fictional-candidate-only",
    "proposal_ref": "proposal:fictional",
    "source_revision_ref": "wiki-revision:proposal",
    "policy_revision_ref": "wiki-revision:historical-rule",
    "event_source_revision_refs": ["wiki-revision:proposal", "wiki-revision:discussion"],
    "created_property_ref": "P2738",
    "recorded_judgement": "approve",
    "record_completeness": "reviewable",
    "holds": [],
    "authority": {
        "candidate_only": True, "semantic_truth_promoted": False,
        "community_consensus_verified": False, "actor_authority_verified": False,
        "wikidata_edit_authorised": False, "ao_dispatch_allowed": False,
        "slr_s29_review_bypassed": False,
    },
}

def _attach(bundle, assessment=HISTORY):
    return attach_deliberation_context(
        bundle, assessment,
        consumer_ref="consumer:OCTF-fixture",
        consumer_scope_ref="matter:fixture",
        source_alignment_ref="candidate:unverified-source-correspondence",
    )

def test_p2738_real_disjointness_bundle_uses_actual_pid_carrier_and_no_mutation():
    bundle = build_wikidata_lane_bundle("disjointness_report")
    old=deepcopy(bundle)
    joined = _attach(bundle)
    assert joined["candidate_properties"] == old["candidate_properties"]
    assert bundle == old
    assert joined["dependency_cone"] == old["dependency_cone"]
    p=joined["deliberation_context"]
    assert p["source_consumer_pid_intersection"] == ["P2738"]
    assert p["consumer_lane_id"] == "disjointness_report"
    assert not p["wikidata_edit_authorised"]
    assert not p["ao_dispatch_allowed"]
    assert p["consumer_source_reopen_status"] == "not_attempted"
    assert p["source_alignment_verification"] == "unverified"
    assert p["independent_structural_diagnostics_retained"]

@pytest.mark.parametrize("lane", [
    "change_review_packet", "climate_review_demonstrator", "hotspot_eval",
    "nat_live_follow_preflight",
])
def test_actual_other_lane_bundles_preserve_unrelated_history_as_non_authority(lane):
    bundle=build_wikidata_lane_bundle(lane)
    result=_attach(bundle)
    assert result["deliberation_context"]["consumer_lane_id"] == lane
    assert result["deliberation_context"]["source_consumer_pid_intersection"] == []
    assert result["promotion_status"] == bundle["promotion_status"]
    assert result["residuals"] == bundle["residuals"]
    assert result["receipts"] == bundle["receipts"]
    assert result["candidate_properties"] == bundle["candidate_properties"]

def test_wrong_or_weak_source_id_does_not_create_a_history_match():
    bundle=build_wikidata_lane_bundle("disjointness_report")
    history=deepcopy(HISTORY)
    history["created_property_ref"]="P10322"
    assert _attach(bundle,history)["deliberation_context"]["source_consumer_pid_intersection"] == []
    # A claimed PID is insufficient without the *same* observed candidate
    # property inside the existing emitted dependency cone.
    bundle["dependency_cone"]["focus_pids"]=[]
    assert _attach(bundle)["deliberation_context"]["source_consumer_pid_intersection"] == []

@pytest.mark.parametrize("mutation", [
    lambda h,b: h["authority"].update({"wikidata_edit_authorised":True}),
    lambda h,b: h["authority"].update({"community_consensus_verified":True}),
    lambda h,b: h["authority"].pop("slr_s29_review_bypassed"),
    lambda h,b: h.update({"version":"future-unsourced"}),
    lambda h,b: h.update({"event_source_revision_refs":[]}),
    lambda h,b: h.update({"created_property_ref":"not-PID"}),
    lambda h,b: b.update({"promotion_status":"approved"}),
    lambda h,b: b.update({"schema_version":"invented"}),
    lambda h,b: b.update({"authority_posture":"edit_bot"}),
])
def test_fail_closed_on_claim_promotion_invented_version_or_missing_provenance(mutation):
    b=build_wikidata_lane_bundle("disjointness_report")
    h=deepcopy(HISTORY)
    mutation(h,b)
    with pytest.raises(ValueError):
        _attach(b,h)

def test_repeated_sidecar_is_not_silently_overwritten():
    bundle=build_wikidata_lane_bundle("disjointness_report")
    with pytest.raises(ValueError, match="already has"):
        _attach(_attach(bundle))
