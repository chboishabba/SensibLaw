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


def test_real_p10322_historical_locator_can_replay_exact_source_byte_spans():
    import hashlib
    import json
    from pathlib import Path
    from src.ontology.wikidata_signal_review_bundle import project_historical_source_anchors

    # Synthetic text for source-span mechanics, real event metadata/oldid from
    # archived P10322. The real wikitext must be pulled at oldid=1572799769.
    fixture=Path(__file__).parent / "fixtures" / "wikidata" / "p10322_history_primary_20220204.json"
    case=json.loads(fixture.read_text(encoding="utf-8"))
    assert case["historical_policy_oldid"] is None
    assert case["community_consensus_verified"] is False
    assert case["property_ref"] == "P10322"
    text = "\n".join(f"source-event-{i} {event['signature_needle']} actor {event['actor_ref']}"
                     for i,event in enumerate(case["events"]))
    snap={
        "wiki":"wikidata","title":case["proposal_title"],
        "revid":case["observed_proposal_oldid"],
        "rev_timestamp":"2022-02-04T13:07:59Z", # fictional second, within observed minute
        "wikitext":text,
    }
    out=project_historical_source_anchors(snap,case)
    assert out["canonical_text_byte_length"] == len(text.encode("utf-8"))
    assert out["source_content_digest_ref"] == "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert out["source_revision_ref"] == "wikidata:page:1572799769"
    assert len(out["event_anchors"]) == 7
    assert out["historical_policy_source_authenticated"] is False
    assert out["source_revision_reopened_in_slr"] is False
    assert out["wikidata_edit_authorised"] is False
    for e,anchor in zip(case["events"],out["event_anchors"]):
        piece=text.encode("utf-8")[anchor["start_byte"]:anchor["end_byte"]]
        assert piece.decode("utf-8") == e["signature_needle"]
        assert "sha256:" + hashlib.sha256(piece).hexdigest() == anchor["excerpt_digest_ref"]
    bad=deepcopy(snap)
    bad["revid"] += 1
    with pytest.raises(ValueError,match="revision"):
        project_historical_source_anchors(bad,case)
    bad=deepcopy(snap)
    bad["title"]="Wikidata:Property proposal/other"
    with pytest.raises(ValueError,match="title"):
        project_historical_source_anchors(bad,case)
    bad=deepcopy(snap)
    bad["wikitext"]=text + "\n" + case["events"][0]["signature_needle"]
    with pytest.raises(ValueError,match="not uniquely"):
        project_historical_source_anchors(bad,case)
    bad=deepcopy(snap)
    bad["rev_timestamp"]="2022-02-05T13:07:59Z"
    with pytest.raises(ValueError,match="timestamp"):
        project_historical_source_anchors(bad,case)


def test_cli_lane_bundle_optional_deliberation_overlay_does_not_add_new_cli_gateway(tmp_path):
    import json
    from cli.__main__ import main
    assessment=tmp_path/"candidate_history.json"
    assessment.write_text(json.dumps(HISTORY),encoding="utf-8")
    output=tmp_path/"bundle.json"
    status=main([
        "wikidata","lane-bundle","--lane","disjointness_report",
        "--deliberation-assessment",str(assessment),
        "--consumer-ref","consumer:fixture",
        "--consumer-scope-ref","matter:fixture",
        "--source-alignment-ref","candidate:unverified",
        "--output",str(output),
    ])
    assert status in (None,0)
    report=json.loads(output.read_text(encoding="utf-8"))
    assert report["deliberation_context"]["source_consumer_pid_intersection"] == ["P2738"]
    assert report["deliberation_context"]["source_alignment_verification"] == "unverified"


def test_existing_mediawiki_fetcher_pins_policy_as_of_and_rejects_wrong_revision(monkeypatch):
    from scripts import wiki_pull_api as mw

    calls=[]
    def fetched(url, *, timeout_s, pacer):
        calls.append(url)
        return {"query":{"pages":[{
            "title":"Wikidata:Property creation","pageid":12345,
            "revisions":[{
                "revid":1180000000,"timestamp":"2022-02-02T18:22:00Z",
                "slots":{"main":{"content":"Historically revised property policy text"}}
            }],
        }]}}
    monkeypatch.setattr(mw,"_get_json",fetched)
    snapshot=mw._fetch_latest_wikitext(
        wiki="wikidata",title="Wikidata:Property creation",
        max_links=0,max_categories=0,include_wikitext=True,
        timeout_s=2,pacer=None,at_or_before="2022-02-04T13:07:00Z",
    )
    assert snapshot.revid == 1180000000
    assert snapshot.wikitext == "Historically revised property policy text"
    assert "www.wikidata.org/w/api.php" in calls[0]
    assert "rvstart=2022-02-04T13%3A07%3A00Z" in calls[0]
    assert "rvdir=older" in calls[0]
    def newer(url, *, timeout_s, pacer):
        return {"query":{"pages":[{
            "title":"Wikidata:Property creation","pageid":12345,
            "revisions":[{
                "revid":12345,"timestamp":"2022-02-05T00:00:00Z",
                "slots":{"main":{"content":"future content"}}
            }],
        }]}}
    monkeypatch.setattr(mw,"_get_json",newer)
    with pytest.raises(ValueError,match="as-of"):
        mw._fetch_latest_wikitext(
            wiki="wikidata",title="Wikidata:Property creation",
            max_links=0,max_categories=0,include_wikitext=True,
            timeout_s=2,pacer=None,at_or_before="2022-02-04T13:07:00Z",
        )
    with pytest.raises(ValueError,match="exact requested"):
        mw._fetch_revision_wikitext(
            wiki="wikidata",title="Wikidata:Property creation",revid=1572799769,
            max_links=0,max_categories=0,include_wikitext=True,
            timeout_s=2,pacer=None,
        )


def test_two_real_revision_shapes_emit_exact_native_slr_handoff_and_hold_missing_policy_authority(tmp_path):
    import json
    from pathlib import Path
    from cli.__main__ import main
    from src.ontology.wikidata_signal_review_bundle import build_historical_source_handoff

    fixture=Path(__file__).parent/"fixtures"/"wikidata"/"p10322_history_primary_20220204.json"
    case=json.loads(fixture.read_text(encoding="utf-8"))
    # A fake text body tests the exact SHA256/byte carrier and CLI contract.
    # The fixture names the real oldid and humans, but no actual fetched source
    # or historical policy consensus is asserted by this regression.
    text="\n".join(row["signature_needle"] for row in case["events"])
    p={
        "wiki":"wikidata","title":case["proposal_title"],
        "revid":1572799769,"rev_timestamp":"2022-02-04T13:07:32Z",
        "wikitext":text,
        "api_url":"https://www.wikidata.org/w/api.php?action=query&revids=1572799769",
    }
    policy={
        "wiki":"wikidata","title":case["historical_policy_title"],
        "revid":1300000000,"rev_timestamp":"2022-01-01T05:04:00Z",
        "wikitext":"FAKE policy fixture, not authentic historical Wikidata text",
        "api_url":"https://www.wikidata.org/w/api.php?action=query&revids=1300000000",
    }
    out=build_historical_source_handoff(p,policy,case,policy_minimum_age_seconds=7*86400)
    native=out["itir_slr_input"]
    assert native["deliberation"]["created_property_ref"] == "P10322"
    assert native["deliberation"]["policy_revision_ref"].startswith("source-revision:sha256:")
    assert native["deliberation"]["source_revision_ref"].startswith("source-revision:sha256:")
    assert native["deliberation"]["policy_revision_ref"] != native["deliberation"]["source_revision_ref"]
    assert len(out["slr_source_inputs"]) == 2
    assert all(row["envelope"]["source_revision_ref"].startswith("source-revision:sha256:")
               for row in out["slr_source_inputs"])
    assert {row["envelope"]["source_revision_ref"] for row in out["slr_source_inputs"]} == set(out["source_revision_refs"])
    assert native["deliberation"]["events"][-1]["judgement"] == "approve"
    assert "authority_receipt_ref" not in native["deliberation"]["events"][-1]
    assert len(native["source_seals"]) == 2
    assert len(native["event_anchors"]) == 7
    assert all(row["source_revision_ref"] == native["deliberation"]["source_revision_ref"]
               for row in native["event_anchors"])
    assert out["slr_source_inputs"][0]["envelope"]["source_ref"] == "wikidata:page:1572799769"
    assert not out["creator_role_verified"]
    assert not out["community_consensus_verified"]
    assert not out["source_ingested_and_reopened_in_slr"]
    assert not out["wikidata_edit_authorised"]

    proposals=tmp_path/"proposal.json"
    policies=tmp_path/"policy.json"
    output=tmp_path/"handoff.json"
    proposals.write_text(json.dumps(p),encoding="utf-8")
    policies.write_text(json.dumps(policy),encoding="utf-8")
    main([
        "wikidata","history-snapshot-handoff",
        "--proposal-snapshot",str(proposals),
        "--policy-snapshot",str(policies),
        "--case-manifest",str(fixture),
        "--policy-minimum-age-seconds",str(7*86400),
        "--output",str(output),
    ])
    assert json.loads(output.read_text(encoding="utf-8"))==out

    newer=deepcopy(policy)
    newer["rev_timestamp"]="2022-02-05T00:00:00Z"
    with pytest.raises(ValueError,match="proposal time"):
        build_historical_source_handoff(p,newer,case,policy_minimum_age_seconds=7*86400)
    later=deepcopy(policy)
    later["rev_timestamp"]="2022-02-01T00:00:00Z"  # after initiation but before closure
    with pytest.raises(ValueError,match="proposal time"):
        build_historical_source_handoff(p,later,case,policy_minimum_age_seconds=7*86400)
    wrong=deepcopy(policy)
    wrong["api_url"]="https://attacker.invalid/fake-revision"
    with pytest.raises(ValueError,match="query origin"):
        build_historical_source_handoff(p,wrong,case,policy_minimum_age_seconds=7*86400)
