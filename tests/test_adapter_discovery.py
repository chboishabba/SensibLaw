"""Tests for the predicate-based adapter discovery registry.

Validates that:
- Content sniffers correctly score their target input types.
- The registry returns the best-scoring adapter.
- UnsupportedInputError carries a structured diagnostic.
- AmbiguousInputError is raised when two adapters tie.
- No adapter_hint, profile, kind, or lane selector appears on
  build_world_model.
"""

from __future__ import annotations

import inspect

import pytest

from sensiblaw import build_world_model
from src.policy.adapter_discovery import (
    AdapterChainResult,
    AdapterRegistration,
    AmbiguousInputError,
    InputDiagnostic,
    UnsupportedInputError,
    clear_registry,
    discover_adapter,
    list_registered_adapters,
    register_adapter,
)
from src.policy.world_model_inputs import normalize_input_envelope


# -- Helpers ------------------------------------------------------------------

def _envelope(payload):
    return normalize_input_envelope(payload)


# -- Registry mechanics -------------------------------------------------------

class TestRegistryMechanics:
    """Test the adapter registry in isolation."""

    def test_clear_and_register(self):
        original = list_registered_adapters()
        try:
            clear_registry()
            assert list_registered_adapters() == []

            reg = AdapterRegistration(
                adapter_id="test_adapter",
                can_handle=lambda p: 0.5,
            )
            register_adapter(reg)
            assert len(list_registered_adapters()) == 1
            assert list_registered_adapters()[0].adapter_id == "test_adapter"
        finally:
            # Restore built-in registrations.
            clear_registry()
            for r in original:
                register_adapter(r)

    def test_duplicate_registration_rejected(self):
        original = list_registered_adapters()
        try:
            clear_registry()
            reg = AdapterRegistration(adapter_id="dup", can_handle=lambda p: 0.5)
            register_adapter(reg)
            with pytest.raises(ValueError, match="already registered"):
                register_adapter(reg)
        finally:
            clear_registry()
            for r in original:
                register_adapter(r)

    def test_empty_registry_raises_unsupported(self):
        original = list_registered_adapters()
        try:
            clear_registry()
            with pytest.raises(UnsupportedInputError) as exc_info:
                discover_adapter(_envelope("anything"))
            assert exc_info.value.diagnostic.status == "unsupported_input"
            assert "empty" in exc_info.value.diagnostic.message
        finally:
            clear_registry()
            for r in original:
                register_adapter(r)

    def test_ambiguous_adapters_raise_diagnostic(self):
        original = list_registered_adapters()
        try:
            clear_registry()
            reg_a = AdapterRegistration(adapter_id="a", can_handle=lambda p: 0.8)
            reg_b = AdapterRegistration(adapter_id="b", can_handle=lambda p: 0.8)
            register_adapter(reg_a)
            register_adapter(reg_b)
            with pytest.raises(AmbiguousInputError) as exc_info:
                discover_adapter(_envelope("test"))
            diag = exc_info.value.diagnostic
            assert diag.status == "ambiguous_input"
            assert set(diag.candidate_adapters) == {"a", "b"}
        finally:
            clear_registry()
            for r in original:
                register_adapter(r)


# -- Content sniffing ---------------------------------------------------------

class TestContentSniffing:
    """Test that the built-in adapters discover input from content."""

    def test_au_bundle_detected(self):
        bundle = {
            "version": "fact.review.bundle.v1",
            "run": {"fact_run_id": "f1", "semantic_run_id": "s1"},
            "review_queue": [],
            "compiler_contract": {},
            "promotion_gate": {},
            "workflow_summary": {},
            "operator_workflow_surface": {},
        }
        result = discover_adapter(_envelope(bundle))
        assert result.adapter_id == "au_review_bundle"
        assert result.score == 1.0

    def test_gwb_broader_review_detected(self):
        payload = {"fixture_kind": "gwb_broader_review", "data": []}
        result = discover_adapter(_envelope(payload))
        assert result.adapter_id == "gwb_broader_review"
        assert result.score == 1.0

    def test_gwb_narrative_detected(self):
        payload = {"per_event": [{"id": "e1"}], "run_id": "run-1"}
        result = discover_adapter(_envelope(payload))
        assert result.adapter_id == "gwb_narrative_timeline"
        assert result.score == 0.9

    def test_brexit_records_detected(self):
        records = [
            {"doc_id": "d1", "title": "T1", "collection": "c1", "url": "http://example.com"},
            {"doc_id": "d2", "title": "T2", "collection": "c2", "url": "http://example.com"},
        ]
        result = discover_adapter(_envelope(records))
        assert result.adapter_id == "brexit_records"
        assert result.score == 0.9

    def test_nat_profile_detected(self):
        payload = {
            "schema_version": "sl.nat_wikidata_profile.v0_1",
            "profile_id": "climate_review_demonstrator",
        }
        result = discover_adapter(_envelope(payload))
        assert result.adapter_id == "nat_profile"
        assert result.score == 1.0

    def test_plain_text_falls_to_generic(self):
        result = discover_adapter(_envelope("Just some plain text."))
        assert result.adapter_id == "generic_input"
        assert result.score == 0.01

    def test_empty_mapping_falls_to_generic(self):
        result = discover_adapter(_envelope({}))
        assert result.adapter_id == "generic_input"
        assert result.score == 0.01


# -- Product boundary ---------------------------------------------------------

class TestProductBoundary:
    """Enforce that the public API accepts data, not adapter names."""

    def test_build_world_model_has_no_adapter_selector_parameter(self):
        sig = inspect.signature(build_world_model)
        forbidden = {"adapter_hint", "profile", "kind", "lane", "adapter"}
        intersection = forbidden & set(sig.parameters)
        assert not intersection, f"build_world_model has forbidden parameters: {intersection}"


# -- Diagnostic structure -----------------------------------------------------

class TestDiagnosticStructure:
    """Validate diagnostic serialisation."""

    def test_diagnostic_to_dict(self):
        diag = InputDiagnostic(
            status="unsupported_input",
            detected={"input_kind": "binary"},
            missing_capabilities=["binary_content_parsing"],
            candidate_adapters=[],
            message="No adapter.",
        )
        d = diag.to_dict()
        assert d["status"] == "unsupported_input"
        assert d["missing_capabilities"] == ["binary_content_parsing"]
        assert d["candidate_adapters"] == []
        assert d["message"] == "No adapter."
