#!/usr/bin/env python3
"""Explicitly acquire and register one bounded legal source revision.

This command is intentionally separate from catalogue compilation. It requires
an operator authorization reference and never asserts applicability or truth.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pnf.legal_source_registry import RegisteredLegalSource  # noqa: E402
from src.policy.corpus_compilation import default_compiler_context  # noqa: E402
from src.policy.postgres_corpus_compilation import (  # noqa: E402
    _canonical_source_coordinates,
    _operational_document_ref,
)
from src.sources.admission import (  # noqa: E402
    AU_PRIMARY_LEGAL_SOURCE_PROFILE,
    admit_source,
)
from src.sources.governed_acquisition import (  # noqa: E402
    AcquisitionPolicy,
    AcquisitionRequest,
    FetchedSource,
    acquire_legal_source,
)
from src.storage.postgres.batched_compiler_store import (  # noqa: E402
    BatchedPostgresCompilerStore,
)
from src.storage.postgres.legal_source_store import (  # noqa: E402
    persist_governed_acquisition_receipt,
    persist_legal_source_revision,
    persist_source_admission_receipts,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--operator-authorization-ref", required=True)
    parser.add_argument("--provider-profile-ref", required=True)
    parser.add_argument("--allowed-host", action="append", required=True)
    parser.add_argument("--maximum-bytes", type=int, default=5_000_000)
    parser.add_argument("--jurisdiction-ref", required=True)
    parser.add_argument("--source-role", required=True)
    parser.add_argument("--authority-level", required=True)
    parser.add_argument("--temporal-ref", action="append", default=[])
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def _fetch(url: str, maximum_bytes: int) -> FetchedSource:
    request = Request(
        url,
        headers={"User-Agent": "SensibLaw governed acquisition/0.1"},
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - explicit CLI boundary
        media_type = response.headers.get_content_type()
        raw = response.read(maximum_bytes + 1)
        final_url = response.geturl()
    if len(raw) > maximum_bytes:
        raise ValueError("response exceeds configured byte limit")
    if media_type not in {"text/plain", "text/html", "application/xhtml+xml"}:
        raise ValueError("this acquisition CLI accepts text and HTML only")
    decoded = raw.decode("utf-8")
    canonical_text, _, _ = _canonical_source_coordinates(
        media_type=media_type,
        source_text=decoded,
        source_ref=f"governed-fetch:{hashlib.sha256(raw).hexdigest()}",
    )
    return FetchedSource(
        final_url=final_url,
        media_type=media_type,
        raw_bytes=raw,
        canonical_text=canonical_text,
    )


def main() -> int:
    args = _args()
    request = AcquisitionRequest(
        requested_url=args.url,
        operator_authorization_ref=args.operator_authorization_ref,
        provider_profile_ref=args.provider_profile_ref,
        source_role=args.source_role,
        jurisdiction_ref=args.jurisdiction_ref,
        authority_level=args.authority_level,
        temporal_refs=tuple(sorted(set(args.temporal_ref))),
    )
    policy = AcquisitionPolicy(
        provider_profile_ref=args.provider_profile_ref,
        allowed_hosts=tuple(sorted(set(args.allowed_host))),
        maximum_bytes=args.maximum_bytes,
        allowed_media_types=("text/plain", "text/html", "application/xhtml+xml"),
    )
    receipt, payload = acquire_legal_source(request, policy=policy, fetch=_fetch)
    store = BatchedPostgresCompilerStore.connect(args.database_url)
    try:
        with store.transaction() as cursor:
            persist_governed_acquisition_receipt(cursor, receipt.to_dict())
            if payload is None:
                print(receipt.to_dict())
                return 1
            context = default_compiler_context()
            canonical_text, canonical_sha256_hex, adapter_ref = (
                _canonical_source_coordinates(
                    media_type=str(payload["media_type"]),
                    source_text=str(payload["canonical_text"]),
                    source_ref=str(payload["source_revision_ref"]),
                )
            )
            if canonical_sha256_hex != str(payload["canonical_text_sha256"]):
                raise ValueError("acquisition canonical text digest is not reproducible")
            document_ref = _operational_document_ref(
                source_content_sha256=str(receipt.content_sha256),
                canonical_text_sha256=canonical_sha256_hex,
                media_type=str(payload["media_type"]),
                media_adapter_ref=adapter_ref,
                context=context,
            )
            admission = admit_source(
                {
                    "source_revision_ref": payload["source_revision_ref"],
                    "source_role": args.source_role,
                    "semantic_scope": "primary_legal_source",
                },
                profile=AU_PRIMARY_LEGAL_SOURCE_PROFILE,
            )
            if not admission.compile_eligible:
                raise ValueError("acquired source role is not admitted as primary law")
            store.persist_context(cursor, context.to_dict())
            store.persist_source_document(
                cursor,
                document_ref=document_ref,
                media_type=str(payload["media_type"]),
                content_sha256=str(receipt.content_sha256),
                source_bytes=bytes(payload["raw_bytes"]),
                canonical_text=canonical_text,
                adapter_ref=adapter_ref,
                adapter_version=context.media_normalization_ref,
                compiler_context_ref=context.context_ref,
                normalization_ref=context.media_normalization_ref,
            )
            persist_source_admission_receipts(
                cursor,
                corpus_ref="corpus:governed-legal-sources",
                receipts=(admission,),
            )
            registered = RegisteredLegalSource(
                source_revision_ref=str(payload["source_revision_ref"]),
                document_ref=document_ref,
                admission_receipt_ref=admission.receipt_ref,
                acquisition_receipt_ref=receipt.receipt_ref,
                jurisdiction_ref=args.jurisdiction_ref,
                source_role=args.source_role,
                authority_level=args.authority_level,
                canonical_text_sha256=canonical_sha256_hex,
                media_type=str(payload["media_type"]),
                temporal_refs=tuple(sorted(set(args.temporal_ref))),
                provider_profile_refs=(args.provider_profile_ref,),
            )
            persist_legal_source_revision(cursor, registered)
        print({"acquisition": receipt.to_dict(), "registered": registered.to_dict()})
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
