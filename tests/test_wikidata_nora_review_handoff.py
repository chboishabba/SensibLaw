"""Bounded NORA projections, attribution, replay and Nat split negative controls."""
from __future__ import annotations

from copy import deepcopy

import pytest

from src.ontology.wikidata_nora_review_handoff import (
    build_nora_review_handoff,
    check_nora_revision,
    nora_acquisition_route,
    replay_nora_review_handoff,
)


def source() -> dict:
    return {
        "candidate_ref": "nat:Q10403939:P5991:rev1",
        "source_field_ref": "field:climate-emissions",
        "source_revision_ref": "wikidata:Q10403939:oldid:123",
        "target_property_ref": "P14143",
        "classification": "split_required",
        "unit": "tonnes CO2e",
        "source_statement_rank": "normal",
        "source_qualifiers": {"P585": "2019"},
        "source_references": [{"P854": "source:report:2019"}],
        "attribution": [
            {"actor_ref": "actor:original-publisher", "role": "source_creator", "source_ref": "source:report:2019"},
            {"actor_ref": "actor:curator", "role": "candidate_proposer", "source_ref": "source:curator:receipt"},
        ],
        "split_plan": {
            "source_statement_guids": ["Q10403939$source-guid"],
            "target_statement_bundles": [
                {"target_ref": "split:scope1", "qualifiers": {"P585": "2019"}},
                {"target_ref": "split:scope2", "qualifiers": {"P585": "2020"}},
            ],
            "reference_transfer": "review_required",
        },
    }


def review(choice="valid") -> dict:
    value = {
        "review_ref": "review:1", "reviewer_ref": "reviewer:1",
        "standpoint_ref": "naya:source-curator", "source_revision_ref": "wikidata:Q10403939:oldid:123",
        "choice": choice,
    }
    if choice in {"invalid", "ambiguous", "modeling_gap"}:
        value["reason_refs"] = ["residual:typed:1"]
    return value


def check(result="unresolved", consumer="climate:whole-period", witness=None):
    value = {"consumer_ref": consumer, "standpoint_ref": "naya:climate-query",
             "source_revision_ref": "wikidata:Q10403939:oldid:123", "result": result}
    if witness:
        value["witness_ref"] = witness
    return value


def test_valid_is_not_global_truth_or_edit_authority():
    out = build_nora_review_handoff(source_candidate=source(), review=review())
    assert out["choice_kind"] == "review_judgement"
    assert out["global_mapping_validity_paid"] is False
    assert out["external_edit_authority_paid"] is False
    assert out["semantic_truth_paid"] is False
    assert out["source_candidate"]["split_plan"]["reference_transfer"] == "review_required"
    assert replay_nora_review_handoff(out) == out


def test_invalid_is_consumer_specific_not_global_refutation():
    out = build_nora_review_handoff(
        source_candidate=source(), review=review("invalid"),
        consumer_checks=[check("non_descent_claim", witness="witness:collision"),
                         check("sufficient_claim", consumer="climate:display", witness="witness:factor")],
    )
    assert out["consumer_checks"][0]["result"] == "non_descent_claim"
    assert out["consumer_checks"][1]["result"] == "sufficient_claim"
    assert out["global_mapping_validity_paid"] is False
    assert out["reported_consumer_results_not_kernel_proofs"] is True


@pytest.mark.parametrize("choice,kind", [
    ("valid", "review_judgement"), ("invalid", "review_judgement"),
    ("ambiguous", "unresolved_judgement"), ("manual_search", "acquisition_request"),
    ("modeling_gap", "model_residual")])
def test_five_choices_keep_distinct_axes(choice, kind):
    out = build_nora_review_handoff(source_candidate=source(), review=review(choice))
    assert out["choice_kind"] == kind
    assert out["review"]["choice"] == choice
    assert out["promotion_authority_paid"] is False


def test_manual_search_is_a_plan_not_a_completed_fetch():
    out = build_nora_review_handoff(source_candidate=source(), review=review("manual_search"))
    route = nora_acquisition_route(out)
    assert route["requested"] is True
    assert route["provider_execution_performed"] is False


def test_source_revision_drift_requires_review_and_no_slr_persistence_claim():
    out = build_nora_review_handoff(source_candidate=source(), review=review())
    same = check_nora_revision(out, "wikidata:Q10403939:oldid:123")
    different = check_nora_revision(out, "wikidata:Q10403939:oldid:124")
    assert same["review_recheck_required"] is False
    assert different["review_recheck_required"] is True
    assert different["slr_reopening_performed"] is False


def test_split_cannot_be_flattened_to_one_target():
    s = source()
    s["split_plan"]["target_statement_bundles"].pop()
    with pytest.raises(ValueError, match="two or more"):
        build_nora_review_handoff(source_candidate=s, review=review())


def test_cannot_drop_source_attribution():
    s = source()
    s["attribution"] = []
    with pytest.raises(ValueError, match="attribution"):
        build_nora_review_handoff(source_candidate=s, review=review())


def test_cannot_change_source_revision_silently():
    r = review()
    r["source_revision_ref"] = "wikidata:Q10403939:oldid:124"
    with pytest.raises(ValueError, match="revision mismatch"):
        build_nora_review_handoff(source_candidate=source(), review=r)


def test_cannot_mutate_source_or_review_after_receipt():
    out = build_nora_review_handoff(source_candidate=source(), review=review())
    for payload in ("source_candidate", "review", "consumer_checks"):
        changed = deepcopy(out)
        if payload == "consumer_checks":
            changed[payload].append(check())
        else:
            changed[payload]["extra_unknown_field"] = "changed"
        with pytest.raises(ValueError, match="replay mismatch"):
            replay_nora_review_handoff(changed)


def test_unknown_choice_or_missing_negative_reason_fail_closed():
    with pytest.raises(ValueError, match="unknown NORA"):
        build_nora_review_handoff(source_candidate=source(), review=review("approve_all"))
    r = review("invalid")
    del r["reason_refs"]
    with pytest.raises(ValueError, match="reason"):
        build_nora_review_handoff(source_candidate=source(), review=r)


def test_source_is_detached_and_unknown_fields_survive_replay():
    s = source()
    out = build_nora_review_handoff(source_candidate=s, review=review())
    s["unit"] = "altered"
    assert out["source_candidate"]["unit"] == "tonnes CO2e"
    assert out["source_candidate"]["source_qualifiers"] == {"P585": "2019"}
    assert out["source_candidate"]["source_references"] == [{"P854": "source:report:2019"}]
    assert replay_nora_review_handoff(out) == out


def _scope_receipts():
    name = {
        "version": "itir.zelph.audited_name_lookup.v1",
        "qid": "Q10403939",
        "graph_revision": "hf:immutable-full-graph",
        "status": "found-in-inspected-objects",
        "candidate_nodes": [{"shard_id": "name-1", "node_id": 24721153}],
        "collision": False,
        "complete_for_source_graph": False,
        "negative_query_authority": False,
        "candidate_only": True,
    }
    closure = {
        "version": "itir.zelph.query_family_closure_audit.v1",
        "graph_revision": "hf:immutable-full-graph",
        "coverage_status": "incomplete",
        "missing_dependencies": {"P14143": ["native-statement-bundle"]},
        "scoped_negative_answer_permitted": False,
        "candidate_only": True,
    }
    return name, closure


def test_scoped_zelph_plan_keeps_graph_and_nora_evidence_separate():
    from src.ontology.wikidata_nora_review_handoff import plan_nora_zelph_scoped_review
    s = source()
    s["subject_qid"] = "Q10403939"
    handoff = build_nora_review_handoff(source_candidate=s, review=review("ambiguous"))
    name, closure = _scope_receipts()
    out = plan_nora_zelph_scoped_review(
        handoff, subject_qid="Q10403939", name_lookup=name, query_closure=closure
    )
    assert out["physical_candidate_nodes"][0]["node_id"] == 24721153
    assert out["review_choice"] == "ambiguous"
    assert out["unresolved_dependencies"] == {"P14143": ["native-statement-bundle"]}
    assert out["source_revision_ref"] != out["graph_revision"]
    assert not out["source_support_paid"] and not out["global_absence_proved"]
    assert not out["slr_s29_persistence_performed"]


def test_scoped_zelph_plan_cannot_promote_absence_or_mix_revisions():
    from src.ontology.wikidata_nora_review_handoff import plan_nora_zelph_scoped_review
    s = source()
    s["subject_qid"] = "Q10403939"
    handoff = build_nora_review_handoff(source_candidate=s, review=review("manual_search"))
    name, closure = _scope_receipts()
    from copy import deepcopy
    wrong_revision = deepcopy(closure)
    wrong_revision["graph_revision"] = "hf:another-graph"
    with pytest.raises(ValueError, match="revision mismatch"):
        plan_nora_zelph_scoped_review(
            handoff, subject_qid="Q10403939", name_lookup=name, query_closure=wrong_revision
        )
    promoted = deepcopy(name)
    promoted["negative_query_authority"] = True
    with pytest.raises(ValueError, match="negative authority"):
        plan_nora_zelph_scoped_review(
            handoff, subject_qid="Q10403939", name_lookup=promoted, query_closure=closure
        )
    missing = deepcopy(name)
    missing["status"] = "unresolved-in-original-graph"
    missing["candidate_nodes"] = []
    out = plan_nora_zelph_scoped_review(
        handoff, subject_qid="Q10403939", name_lookup=missing, query_closure=closure
    )
    assert out["global_absence_proved"] is False
    assert out["name_route_status"] == "unresolved-in-original-graph"
