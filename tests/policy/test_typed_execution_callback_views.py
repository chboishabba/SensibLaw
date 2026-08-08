from __future__ import annotations

from collections.abc import Mapping

from src.pnf.streaming_fixed_point import OwnerKey, SolverJob, SolverReceipt
from src.policy.typed_execution_callback_views import (
    ManifestCallbackView,
    ReceiptCallbackView,
)
from src.storage.postgres.distributed_semantic_execution import ImmutableJobManifest


def _manifest() -> ImmutableJobManifest:
    job = SolverJob(
        owner_key=OwnerKey("document:1", "scope:1", "factor:1"),
        declaration_ref="declaration:1",
        input_revision=3,
        input_refs=("observation:1",),
        input_payload={"observation_delta": {"observations": ()}},
        rule_set_revision="rules:1",
    )
    return ImmutableJobManifest.build(
        job_ref="job:leased",
        run_ref="run:1",
        document_ref="document:1",
        owner_ref="owner:1",
        input_revision=3,
        input_payload=job.to_dict(),
    )


def test_manifest_view_supports_mapping_and_typed_attributes() -> None:
    manifest = _manifest()
    view = ManifestCallbackView(manifest)

    assert isinstance(view, Mapping)
    assert view["job_ref"] == manifest.job_ref
    assert view["input_manifest"]["input_revision"] == 3
    assert view.input_sha256 == manifest.input_sha256


def test_receipt_view_supports_mapping_and_typed_attributes() -> None:
    receipt = SolverReceipt(
        job_ref="job:leased",
        owner_key=OwnerKey("document:1", "scope:1", "factor:1"),
        input_revision=3,
        input_refs=("observation:1",),
        rule_set_revision="rules:1",
        proposals=(),
    )
    view = ReceiptCallbackView(receipt)

    assert isinstance(view, Mapping)
    assert view["job_ref"] == receipt.job_ref
    assert view.job_ref == receipt.job_ref
    assert view["receipt_ref"] == receipt.receipt_ref
