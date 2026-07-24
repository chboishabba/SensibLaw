"""Explicit operator-authorised acquisition of one bounded legal source.

Normal catalogue compilation never imports or calls this module. The caller must
supply an operator authorization, provider policy, and bounded fetcher.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from src.policy.carriers.canonical import canonical_sha256

GOVERNED_ACQUISITION_CONTRACT = "governed-legal-source-acquisition:v0_1"


@dataclass(frozen=True)
class AcquisitionPolicy:
    provider_profile_ref: str
    allowed_hosts: tuple[str, ...]
    maximum_bytes: int
    allowed_media_types: tuple[str, ...] = (
        "text/plain",
        "text/html",
        "application/xhtml+xml",
        "application/pdf",
    )

    def __post_init__(self) -> None:
        if self.maximum_bytes <= 0:
            raise ValueError("acquisition maximum_bytes must be positive")


@dataclass(frozen=True)
class AcquisitionRequest:
    requested_url: str
    operator_authorization_ref: str
    provider_profile_ref: str
    source_role: str
    jurisdiction_ref: str
    authority_level: str
    temporal_refs: tuple[str, ...] = ()

    @property
    def request_ref(self) -> str:
        return "governed-acquisition-request:" + canonical_sha256(asdict(self))


@dataclass(frozen=True)
class FetchedSource:
    final_url: str
    media_type: str
    raw_bytes: bytes
    canonical_text: str


@dataclass(frozen=True)
class AcquisitionReceipt:
    request_ref: str
    operator_authorization_ref: str
    provider_profile_ref: str
    requested_url: str
    final_url: str | None
    source_revision_ref: str | None
    content_sha256: str | None
    media_type: str | None
    byte_count: int
    state: str
    failure_reason: str | None = None

    @property
    def receipt_ref(self) -> str:
        return "governed-acquisition-receipt:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_ref": self.receipt_ref,
            **asdict(self),
            "contract_ref": GOVERNED_ACQUISITION_CONTRACT,
            "network_operation_explicit": True,
            "semantic_state_promoted": False,
            "legal_truth_closed": False,
        }


FetchFunction = Callable[[str, int], FetchedSource]


def _validated_http_host(url: str, allowed_hosts: set[str], *, label: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError(f"{label} URL must use HTTP(S)")
    hostname = str(parsed.hostname or "")
    if hostname not in allowed_hosts:
        raise ValueError(f"{label} host is outside the acquisition policy")
    return hostname


def acquire_legal_source(
    request: AcquisitionRequest,
    *,
    policy: AcquisitionPolicy,
    fetch: FetchFunction,
) -> tuple[AcquisitionReceipt, Mapping[str, Any] | None]:
    """Fetch one explicitly authorised source and return a registry payload."""

    if not request.operator_authorization_ref:
        raise ValueError("operator authorization is required")
    if request.provider_profile_ref != policy.provider_profile_ref:
        raise ValueError("request provider profile disagrees with policy")
    allowed_hosts = set(policy.allowed_hosts)
    _validated_http_host(request.requested_url, allowed_hosts, label="requested")

    try:
        fetched = fetch(request.requested_url, policy.maximum_bytes)
        _validated_http_host(fetched.final_url, allowed_hosts, label="redirected")
        if len(fetched.raw_bytes) > policy.maximum_bytes:
            raise ValueError("fetched source exceeds acquisition byte limit")
        if fetched.media_type not in set(policy.allowed_media_types):
            raise ValueError("fetched source media type is not permitted")
        content_sha256 = hashlib.sha256(fetched.raw_bytes).hexdigest()
        canonical_sha256_hex = hashlib.sha256(
            fetched.canonical_text.encode("utf-8")
        ).hexdigest()
        source_revision_ref = "legal-source-revision:" + canonical_sha256(
            {
                "request_ref": request.request_ref,
                "content_sha256": content_sha256,
                "canonical_text_sha256": canonical_sha256_hex,
                "media_type": fetched.media_type,
            }
        )
        receipt = AcquisitionReceipt(
            request_ref=request.request_ref,
            operator_authorization_ref=request.operator_authorization_ref,
            provider_profile_ref=request.provider_profile_ref,
            requested_url=request.requested_url,
            final_url=fetched.final_url,
            source_revision_ref=source_revision_ref,
            content_sha256=content_sha256,
            media_type=fetched.media_type,
            byte_count=len(fetched.raw_bytes),
            state="persisted",
        )
        registry_payload = {
            "source_revision_ref": source_revision_ref,
            "jurisdiction_ref": request.jurisdiction_ref,
            "source_role": request.source_role,
            "authority_level": request.authority_level,
            "temporal_refs": request.temporal_refs,
            "provider_profile_refs": (request.provider_profile_ref,),
            "media_type": fetched.media_type,
            "canonical_text_sha256": canonical_sha256_hex,
            "raw_bytes": fetched.raw_bytes,
            "canonical_text": fetched.canonical_text,
            "acquisition_receipt_ref": receipt.receipt_ref,
        }
        return receipt, registry_payload
    except Exception as error:
        receipt = AcquisitionReceipt(
            request_ref=request.request_ref,
            operator_authorization_ref=request.operator_authorization_ref,
            provider_profile_ref=request.provider_profile_ref,
            requested_url=request.requested_url,
            final_url=None,
            source_revision_ref=None,
            content_sha256=None,
            media_type=None,
            byte_count=0,
            state="rejected" if isinstance(error, ValueError) else "failed",
            failure_reason=f"{type(error).__name__}: {error}",
        )
        return receipt, None


__all__ = [
    "GOVERNED_ACQUISITION_CONTRACT",
    "AcquisitionPolicy",
    "AcquisitionReceipt",
    "AcquisitionRequest",
    "FetchedSource",
    "acquire_legal_source",
]
