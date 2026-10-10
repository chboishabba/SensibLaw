from __future__ import annotations

import os

import src.ontology.wikidata_nat_hf_compatible_executor as compat_exec


def _selector() -> dict:
    return {
        "candidate_only": True,
        "full_reasoning_required": False,
        "operations": ["node_route_selection", "partial_loading"],
        "qids": ["Q1"],
        "properties": ["P854"],
        "required_outputs": ["statement_snapshot"],
    }


def test_incompatible_binary_blocks_before_strict_scan(monkeypatch) -> None:
    monkeypatch.setattr(compat_exec, "_fetch_manifest_cached", lambda: ({"manifestVersion": "zelph-hf-layout/v2"}, {}))
    monkeypatch.setattr(
        compat_exec,
        "select_compatible_zelph_binary",
        lambda _manifest: {
            "compatible": False,
            "selected_binary": None,
            "candidates": [{"binary": "/usr/bin/zelph", "exit_code": -11}],
        },
    )
    monkeypatch.setattr(
        compat_exec,
        "_strict_evaluate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("strict scan must not run")),
    )

    result = compat_exec.hosted_hf_selector_executor_compatible(_selector())
    assert result["execution_outcome"] == "engine_unavailable"
    assert result["executor_receipt"]["transport_status"] == "zelph_binary_manifest_incompatible"
    assert result["outputs"] == {}


def test_compatible_binary_is_injected_into_strict_executor(monkeypatch) -> None:
    monkeypatch.delenv("ZELPH_BIN", raising=False)
    monkeypatch.setattr(compat_exec, "_fetch_manifest_cached", lambda: ({"manifestVersion": "zelph-hf-layout/v2"}, {}))
    compatibility = {
        "compatible": True,
        "selected_binary": "/known-good/zelph",
        "candidates": [{"binary": "/known-good/zelph", "exit_code": 0}],
    }
    monkeypatch.setattr(compat_exec, "select_compatible_zelph_binary", lambda _manifest: compatibility)

    def strict(_selector, *, manifest, headers):
        assert manifest["manifestVersion"] == "zelph-hf-layout/v2"
        assert headers == {}
        assert os.environ["ZELPH_BIN"] == "/known-good/zelph"
        return {
            "executor_id": "strict",
            "execution_outcome": "executed_no_match",
            "executor_receipt": {"network_performed": True},
            "outputs": {},
        }

    monkeypatch.setattr(compat_exec, "_strict_evaluate", strict)
    result = compat_exec.hosted_hf_selector_executor_compatible(_selector())
    assert result["executor_id"] == compat_exec.COMPAT_EXECUTOR_ID
    assert result["executor_receipt"]["selected_zelph_binary"] == "/known-good/zelph"
    assert result["executor_receipt"]["binary_compatibility"] == compatibility
    assert "ZELPH_BIN" not in os.environ


def test_clean_zelph_unresolved_qid_can_be_confirmed_by_wikidata_entity_export(monkeypatch) -> None:
    selector = _selector()
    selector["qids"] = ["Q1", "Q2"]
    selector["properties"] = ["P14143", "P854"]

    monkeypatch.setattr(compat_exec, "_fetch_manifest_cached", lambda: ({"manifestVersion": "zelph-hf-layout/v2"}, {}))
    compatibility = {
        "compatible": True,
        "selected_binary": "/known-good/zelph",
        "candidates": [{"binary": "/known-good/zelph", "exit_code": 0}],
    }
    monkeypatch.setattr(compat_exec, "select_compatible_zelph_binary", lambda _manifest: compatibility)
    monkeypatch.setattr(
        compat_exec,
        "_strict_evaluate",
        lambda *_args, **_kwargs: {
            "executor_id": "strict",
            "execution_outcome": "executed_with_output",
            "executor_receipt": {
                "network_performed": True,
                "requested_qids": ["Q1", "Q2"],
                "statement_fetch_qids": ["Q1"],
                "unresolved_qids": ["Q2"],
                "all_requested_qids_resolved": False,
                "partial_identity_subset": True,
                "partial_read": {
                    "status": "partial",
                    "resolved_qids": {"Q1": 101},
                    "unresolved_qids": ["Q2"],
                    "failure": None,
                },
            },
            "outputs": {
                "statement_snapshot": {"Q1": {"revid": 1, "claims": {}}},
                "qualifier_snaks": {"Q1": {}},
                "reference_snaks": {"Q1": {}},
                "source_revision_lineage": {"Q1": {"revid": 1}},
                "content_address": "sha256:q1",
            },
        },
    )

    def direct_fetch(qids, properties):
        assert list(qids) == ["Q2"]
        assert list(properties) == ["P14143", "P854"]
        return {
            "statement_snapshot": {"Q2": {"revid": 2, "claims": {}}},
            "qualifier_snaks": {"Q2": {}},
            "reference_snaks": {"Q2": {}},
            "source_revision_lineage": {"Q2": {"revid": 2}},
            "content_address": "sha256:q2",
        }

    monkeypatch.setattr(compat_exec, "fetch_live_wikidata_statement_payload", direct_fetch)
    result = compat_exec.hosted_hf_selector_executor_compatible(selector)

    assert result["execution_outcome"] == "executed_with_output"
    assert sorted(result["outputs"]["statement_snapshot"]) == ["Q1", "Q2"]
    receipt = result["executor_receipt"]
    assert receipt["zelph_unresolved_qids"] == ["Q2"]
    assert receipt["wikidata_direct_identity_confirmed_qids"] == ["Q2"]
    assert receipt["unresolved_qids"] == []
    assert receipt["statement_fetch_qids"] == ["Q1", "Q2"]
    assert receipt["all_requested_qids_resolved"] is True
    assert receipt["partial_identity_subset"] is False
    assert receipt["identity_confirmation_sources"] == {
        "zelph_node_of_name": ["Q1"],
        "wikidata_revision_locked_entity_export": ["Q2"],
        "still_unresolved": [],
    }
    assert receipt["direct_wikidata_fallback_pays_zelph_route_residual"] is False
    assert receipt["direct_wikidata_fallback_pays_source_support"] is False


def test_failed_direct_wikidata_identity_fallback_leaves_residual_open(monkeypatch) -> None:
    selector = _selector()
    selector["qids"] = ["Q2"]

    monkeypatch.setattr(compat_exec, "_fetch_manifest_cached", lambda: ({"manifestVersion": "zelph-hf-layout/v2"}, {}))
    monkeypatch.setattr(
        compat_exec,
        "select_compatible_zelph_binary",
        lambda _manifest: {
            "compatible": True,
            "selected_binary": "/known-good/zelph",
            "candidates": [{"binary": "/known-good/zelph", "exit_code": 0}],
        },
    )
    monkeypatch.setattr(
        compat_exec,
        "_strict_evaluate",
        lambda *_args, **_kwargs: {
            "executor_id": "strict",
            "execution_outcome": "executed_no_match",
            "executor_receipt": {
                "network_performed": True,
                "requested_qids": ["Q2"],
                "statement_fetch_qids": [],
                "unresolved_qids": ["Q2"],
                "all_requested_qids_resolved": False,
                "partial_identity_subset": True,
                "partial_read": {
                    "status": "partial",
                    "resolved_qids": {},
                    "unresolved_qids": ["Q2"],
                    "failure": None,
                },
            },
            "outputs": {},
        },
    )
    monkeypatch.setattr(
        compat_exec,
        "fetch_live_wikidata_statement_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("no live Wikidata revision found for Q2")),
    )

    result = compat_exec.hosted_hf_selector_executor_compatible(selector)
    assert result["execution_outcome"] == "executed_no_match"
    receipt = result["executor_receipt"]
    assert receipt["zelph_unresolved_qids"] == ["Q2"]
    assert receipt["wikidata_direct_identity_confirmed_qids"] == []
    assert receipt["unresolved_qids"] == ["Q2"]
    assert "Q2" in receipt["wikidata_direct_identity_fallback_failures"]
