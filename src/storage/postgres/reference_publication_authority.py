"""Commit compact publication authority after bounded family persistence."""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres.distributed_semantic_execution_store import (
    DistributedSemanticExecutionStore,
)


REFERENCE_EXECUTION_RECEIPT_CONTRACT = "reference-execution-receipt:v1"


def commit_reference_publication_authority(
    cursor: Any,
    *,
    document_ref: str,
    streaming_build: Mapping[str, Any],
    persistence_counts: Mapping[str, int | str],
) -> dict[str, str]:
    """Bind persisted families and atomically commit one publication identity."""

    graph_manifest_ref = str(persistence_counts["graph_manifest_ref"])
    certificate = dict(streaming_build.get("fixed_point_certificate") or {})
    certificate_ref = str(certificate["certificate_ref"])
    owner_fingerprint = dict(streaming_build.get("owner_fingerprint") or {})
    family_manifests = dict(streaming_build.get("family_manifests") or {})
    jobs = dict(family_manifests.get("solver_jobs") or {})
    residuals = dict(family_manifests.get("residuals") or {})
    accepted_job_set_digest = str(jobs.get("ordered_digest") or canonical_sha256([]))
    unresolved_demand_digest = str(
        residuals.get("ordered_digest") or canonical_sha256([])
    )
    coverage_digest = canonical_sha256(
        owner_fingerprint.get("coverage_manifest_ref") or ""
    )
    operation_contract_refs = (
        str(streaming_build.get("reference_finalization_contract") or ""),
        REFERENCE_EXECUTION_RECEIPT_CONTRACT,
    )
    store = DistributedSemanticExecutionStore()
    store.persist_fixed_point_receipt(
        cursor,
        certificate_ref=certificate_ref,
        document_ref=document_ref,
        graph_manifest_ref=graph_manifest_ref,
        document_revision=int(certificate["revision"]),
        accepted_job_set_digest=accepted_job_set_digest,
        unresolved_demand_digest=unresolved_demand_digest,
        coverage_digest=coverage_digest,
        operation_contract_refs=operation_contract_refs,
        local_fixed_point=certificate.get("local_fixed_point") == "reached",
        payload=certificate,
    )

    compact_receipt = {
        "document_ref": document_ref,
        "graph_manifest_ref": graph_manifest_ref,
        "certificate_ref": certificate_ref,
        "owner_fingerprint": owner_fingerprint,
        "family_manifests": {
            family: {
                "record_count": int((descriptor or {}).get("record_count") or 0),
                "byte_count": int((descriptor or {}).get("byte_count") or 0),
                "ordered_digest": str((descriptor or {}).get("ordered_digest") or ""),
            }
            for family, descriptor in sorted(family_manifests.items())
            if isinstance(descriptor, Mapping)
        },
        "persistence_counts": dict(persistence_counts),
        "reference_finalization_contract": str(
            streaming_build.get("reference_finalization_contract") or ""
        ),
        "full_document_payload_embedded": False,
    }
    build_key_sha256 = str(
        streaming_build.get("build_key_sha256")
        or canonical_sha256(
            {
                "document_ref": document_ref,
                "graph_manifest_ref": graph_manifest_ref,
                "certificate_ref": certificate_ref,
            }
        )
    )
    receipt_ref = "semantic-execution-receipt:" + canonical_sha256(compact_receipt)
    store.persist_execution_receipt(
        cursor,
        receipt_ref=receipt_ref,
        document_ref=document_ref,
        graph_manifest_ref=graph_manifest_ref,
        certificate_ref=certificate_ref,
        build_key_sha256=build_key_sha256,
        receipt_contract_ref=REFERENCE_EXECUTION_RECEIPT_CONTRACT,
        payload=compact_receipt,
    )

    publication_identity = {
        "document_ref": document_ref,
        "graph_manifest_ref": graph_manifest_ref,
        "certificate_ref": certificate_ref,
        "execution_receipt_ref": receipt_ref,
    }
    publication_digest = canonical_sha256(publication_identity)
    publication_ref = "publication-build:" + publication_digest
    store.stage_publication(
        cursor,
        publication_ref=publication_ref,
        document_ref=document_ref,
        graph_manifest_ref=graph_manifest_ref,
        certificate_ref=certificate_ref,
        publication_digest=publication_digest,
    )
    store.commit_publication(
        cursor,
        publication_ref=publication_ref,
        expected_digest=publication_digest,
    )
    return {
        "graph_manifest_ref": graph_manifest_ref,
        "certificate_ref": certificate_ref,
        "execution_receipt_ref": receipt_ref,
        "publication_ref": publication_ref,
        "publication_digest": publication_digest,
        "publication_state": "committed",
    }


__all__ = [
    "REFERENCE_EXECUTION_RECEIPT_CONTRACT",
    "commit_reference_publication_authority",
]
