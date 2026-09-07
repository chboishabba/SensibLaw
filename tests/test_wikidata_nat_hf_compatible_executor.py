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
