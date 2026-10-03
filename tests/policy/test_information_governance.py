from __future__ import annotations

import pytest

from src.policy.information_governance import (
    build_information_asset,
    build_processing_activity,
)


def test_information_asset_requires_explicit_pii_and_purpose() -> None:
    asset = build_information_asset(
        asset_ref="asset:inv-source-1",
        data_class="source_evidence",
        contains_pii=True,
        sensitivity="restricted",
        accountable_role="matter_owner",
        purpose_ref="purpose:investigation",
        matter_ref="matter:1",
        access_basis_ref="access:user-authorized",
        allowed_consumer_refs=["consumer:inv"],
        storage_ref="pg:source_revision:1",
        external_provider_refs=[],
        retention_class_ref="retention:matter",
        revocation_or_deletion_state="retained",
        audit_refs=["audit:1"],
    )
    assert asset["contains_pii"] is True
    assert asset["purpose_ref"] == "purpose:investigation"
    assert asset["creates_visibility_authority"] is False
    with pytest.raises(ValueError):
        build_information_asset(**{**asset, "purpose_ref": ""})


def test_processing_activity_links_input_output_without_inventing_visibility() -> None:
    activity = build_processing_activity(
        activity_ref="processing:rel-compare",
        purpose_ref="purpose:investigation",
        input_asset_refs=["asset:source-a", "asset:source-b"],
        output_asset_refs=["asset:comparison"],
        processor_role_ref="role:slr",
        external_provider_refs=[],
        control_refs=["control:source-provenance"],
        evidence_refs=["receipt:comparison:1"],
    )
    assert activity["input_asset_refs"] == ["asset:source-a", "asset:source-b"]
    assert activity["output_asset_refs"] == ["asset:comparison"]
    assert activity["grants_matter_visibility"] is False
