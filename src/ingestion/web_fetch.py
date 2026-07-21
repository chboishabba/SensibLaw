"""Policy-gated HTTP fetches that feed the shared canonical media adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import sys
from typing import Any, Mapping, Protocol, TextIO
from urllib.parse import urldefrag, urlparse

import requests

from src.ingestion.media_adapter import HtmlDocumentMediaAdapter, TextDocumentMediaAdapter
from src.runtime.progress import ProgressEvent, emit_progress


WEB_FETCH_CONTRACT = "web-fetch:v0_1"
_ALLOWED_SCHEMES = frozenset({"http", "https"})


class ResponseLike(Protocol):
    status_code: int
    url: str
    headers: Mapping[str, str]
    content: bytes

    def raise_for_status(self) -> None: ...


class SessionLike(Protocol):
    def get(self, url: str, **kwargs: Any) -> ResponseLike: ...


@dataclass(frozen=True)
class FetchPolicy:
    timeout_seconds: float = 15.0
    max_bytes: int = 5_000_000
    user_agent: str = "SensibLaw-ITIR/0.1 (+bounded research fetch)"
    allowed_hosts: tuple[str, ...] = ()
    allowed_content_types: tuple[str, ...] = (
        "text/html",
        "application/xhtml+xml",
        "text/plain",
    )


@dataclass(frozen=True)
class FetchReceipt:
    requested_url: str
    status: str
    final_url: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    byte_count: int = 0
    content_sha256: str | None = None
    canonical_text_sha256: str | None = None
    error_type: str | None = None
    error_detail: str | None = None
    contract_ref: str = WEB_FETCH_CONTRACT

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value not in (None, "")
        }


@dataclass(frozen=True)
class FetchedWebDocument:
    requested_url: str
    final_url: str | None
    raw_bytes: bytes
    canonical_text: str
    media_type: str | None
    receipt: FetchReceipt

    @property
    def fetched(self) -> bool:
        return self.receipt.status == "fetched"


def normalize_http_url(url: str) -> str | None:
    without_fragment, _fragment = urldefrag(str(url).strip())
    parsed = urlparse(without_fragment)
    if parsed.scheme.casefold() not in _ALLOWED_SCHEMES or not parsed.hostname:
        return None
    return parsed._replace(scheme=parsed.scheme.casefold()).geturl()


def _host_allowed(url: str, policy: FetchPolicy) -> bool:
    if not policy.allowed_hosts:
        return True
    host = (urlparse(url).hostname or "").casefold()
    return any(
        host == allowed.casefold() or host.endswith("." + allowed.casefold())
        for allowed in policy.allowed_hosts
    )


def _content_type(headers: Mapping[str, str]) -> str:
    value = str(headers.get("Content-Type") or headers.get("content-type") or "")
    return value.split(";", 1)[0].strip().casefold()


def _failed(
    url: str,
    *,
    status: str,
    detail: str,
    stream: TextIO,
    error_type: str | None = None,
    final_url: str | None = None,
    status_code: int | None = None,
    content_type: str | None = None,
) -> FetchedWebDocument:
    receipt = FetchReceipt(
        requested_url=url,
        final_url=final_url,
        status=status,
        status_code=status_code,
        content_type=content_type,
        error_type=error_type,
        error_detail=detail,
    )
    emit_progress(
        ProgressEvent(
            phase="url_fetch",
            state=status,
            subject_ref=url,
            message=detail,
        ),
        stream=stream,
    )
    return FetchedWebDocument(url, final_url, b"", "", content_type, receipt)


def fetch_web_document(
    url: str,
    *,
    policy: FetchPolicy | None = None,
    session: SessionLike | None = None,
    progress_stream: TextIO | None = None,
) -> FetchedWebDocument:
    """Fetch one declared URL and return a truthful success or failure receipt."""

    active_policy = policy or FetchPolicy()
    stream = progress_stream or sys.stderr
    normalized = normalize_http_url(url)
    if normalized is None:
        return _failed(
            str(url),
            status="invalid_url",
            detail="only absolute HTTP(S) URLs are supported",
            stream=stream,
        )
    if not _host_allowed(normalized, active_policy):
        return _failed(
            normalized,
            status="blocked_host",
            detail="host is outside the declared fetch policy",
            stream=stream,
        )
    active_session = session or requests.Session()
    try:
        response = active_session.get(
            normalized,
            timeout=active_policy.timeout_seconds,
            headers={"User-Agent": active_policy.user_agent},
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        return _failed(
            normalized,
            status="network_error",
            detail=str(error),
            error_type=type(error).__name__,
            stream=stream,
        )
    final_url = normalize_http_url(response.url) or normalized
    media_type = _content_type(response.headers)
    if media_type not in active_policy.allowed_content_types:
        return _failed(
            normalized,
            status="content_type_rejected",
            detail=f"unsupported content type: {media_type or '<missing>'}",
            final_url=final_url,
            status_code=int(response.status_code),
            content_type=media_type,
            stream=stream,
        )
    raw_bytes = bytes(response.content)
    if len(raw_bytes) > active_policy.max_bytes:
        return _failed(
            normalized,
            status="too_large",
            detail=f"payload exceeds {active_policy.max_bytes} bytes",
            final_url=final_url,
            status_code=int(response.status_code),
            content_type=media_type,
            stream=stream,
        )
    source_text = raw_bytes.decode("utf-8", errors="replace")
    source_ref = "web:" + hashlib.sha256(final_url.encode("utf-8")).hexdigest()
    if media_type in {"text/html", "application/xhtml+xml"}:
        canonical = HtmlDocumentMediaAdapter(
            source_artifact_ref=source_ref,
            provenance={"requested_url": normalized, "final_url": final_url},
        ).adapt(source_text)
    else:
        canonical = TextDocumentMediaAdapter(
            source_artifact_ref=source_ref,
            provenance={"requested_url": normalized, "final_url": final_url},
        ).adapt(source_text)
    receipt = FetchReceipt(
        requested_url=normalized,
        final_url=final_url,
        status="fetched",
        status_code=int(response.status_code),
        content_type=media_type,
        byte_count=len(raw_bytes),
        content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        canonical_text_sha256=hashlib.sha256(
            canonical.text.encode("utf-8")
        ).hexdigest(),
    )
    emit_progress(
        ProgressEvent(
            phase="url_fetch",
            state="fetched",
            completed=1,
            subject_ref=final_url,
            message=f"{len(raw_bytes)} bytes",
        ),
        stream=stream,
    )
    return FetchedWebDocument(
        normalized,
        final_url,
        raw_bytes,
        canonical.text,
        media_type,
        receipt,
    )


__all__ = [
    "FetchPolicy",
    "FetchReceipt",
    "FetchedWebDocument",
    "SessionLike",
    "WEB_FETCH_CONTRACT",
    "fetch_web_document",
    "normalize_http_url",
]
