from __future__ import annotations

import hashlib
import io
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

from src.ingestion.media_adapter import (
    HtmlDocumentMediaAdapter,
    PdfPageMediaAdapter,
    parse_canonical_text,
)
from src.policy.carriers.canonical import canonical_sha256


SOURCE_MEDIA_MATERIALIZATION_SCHEMA_VERSION = (
    "sl.nat_source_media_materialization.v0_1"
)
SOURCE_MEDIA_DISPATCH_SCHEMA_VERSION = "sl.nat_source_media_dispatch.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else ()
    )


def _safe_store_path(root: str | Path, relpath: str) -> Path:
    relative = Path(relpath)
    if not relpath or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("invalid content-addressed artifact relative path")
    root_path = Path(root).resolve()
    path = (root_path / relative).resolve()
    try:
        path.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("artifact path escapes configured store root") from exc
    return path


def _load_verified_artifact(
    receipt: Mapping[str, Any], *, artifact_store_dir: str | Path
) -> bytes:
    if not bool(receipt.get("content_acquired")):
        raise ValueError("media materialization requires acquired source content")
    if not bool(receipt.get("artifact_persisted")):
        raise ValueError("media materialization requires a persisted source artifact")
    digest = _text(receipt.get("content_digest"))
    if not digest.startswith("sha256:"):
        raise ValueError("media materialization requires a sha256 source digest")
    path = _safe_store_path(
        artifact_store_dir,
        _text(receipt.get("artifact_relpath")),
    )
    body = path.read_bytes()
    observed = "sha256:" + hashlib.sha256(body).hexdigest()
    if observed != digest:
        raise ValueError("persisted source artifact no longer matches fetch receipt")
    return body


def _page_text(page: Any) -> str:
    parts: list[str] = []
    for element in page:
        if isinstance(element, LTTextContainer):
            text = element.get_text()
            if text:
                parts.append(text)
    return "".join(parts).strip()


def _pdf_page_records(body: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page_number, page in enumerate(extract_pages(io.BytesIO(body)), start=1):
        records.append(
            {
                "page": page_number,
                "heading": "",
                "text": _page_text(page),
            }
        )
    return records


def _charset_from_content_type(content_type: str) -> str:
    match = re.search(r"charset\s*=\s*['\"]?([^;'\"\s]+)", content_type, re.I)
    return match.group(1).strip() if match else "utf-8"


def _decode_html(body: bytes, content_type: str) -> tuple[str, str, bool]:
    charset = _charset_from_content_type(content_type)
    try:
        return body.decode(charset), charset, False
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace"), "utf-8", True


def _media_kind(body: bytes, content_type: str) -> str:
    normalized = content_type.casefold()
    if "application/pdf" in normalized or body.startswith(b"%PDF"):
        return "pdf"
    stripped = body.lstrip()[:256].casefold()
    if (
        "text/html" in normalized
        or stripped.startswith(b"<!doctype html")
        or stripped.startswith(b"<html")
    ):
        return "html"
    return "unsupported"


def _persist_canonical_json(
    canonical_payload: Mapping[str, Any], *, materialized_store_dir: str | Path
) -> tuple[str, str]:
    digest_hex = canonical_sha256(canonical_payload)
    relpath = Path("canonical") / "sha256" / digest_hex[:2] / f"{digest_hex}.json"
    path = Path(materialized_store_dir) / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (
        json.dumps(
            canonical_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if canonical_sha256(existing) != digest_hex:
            raise ValueError("canonical materialization store digest mismatch")
    else:
        try:
            path.write_text(serialized, encoding="utf-8")
        except FileExistsError:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if canonical_sha256(existing) != digest_hex:
                raise ValueError("canonical materialization store digest mismatch")
    return "sha256:" + digest_hex, relpath.as_posix()


def materialize_source_fetch_receipt(
    receipt: Mapping[str, Any],
    *,
    artifact_store_dir: str | Path,
    materialized_store_dir: str | Path,
) -> dict[str, Any]:
    """Compile one persisted external source artifact to the canonical text carrier.

    This is media materialization only. It creates page/character-addressable text
    and parser structure, but it does not decide whether the source supports any Nat
    proposition and it creates no authority or migration permission.
    """

    source_receipt_ref = _text(receipt.get("receipt_ref"))
    source_digest = _text(receipt.get("content_digest"))
    if not source_receipt_ref or not source_digest:
        raise ValueError("media materialization requires exact fetch receipt identity")

    if not bool(receipt.get("content_acquired")):
        payload_without_ref = {
            "schema_version": SOURCE_MEDIA_MATERIALIZATION_SCHEMA_VERSION,
            "source_fetch_receipt_ref": source_receipt_ref,
            "source_content_digest": source_digest,
            "state": "blocked_source_content_not_acquired",
            "media_kind": "unavailable",
            "source_bytes_reverified": False,
            "canonical_text_created": False,
            "proposition_support_evaluated": False,
            "authority_evaluated": False,
            "semantic_promotion_performed": False,
        }
    elif not bool(receipt.get("artifact_persisted")):
        payload_without_ref = {
            "schema_version": SOURCE_MEDIA_MATERIALIZATION_SCHEMA_VERSION,
            "source_fetch_receipt_ref": source_receipt_ref,
            "source_content_digest": source_digest,
            "state": "blocked_source_artifact_not_persisted",
            "media_kind": "unavailable",
            "source_bytes_reverified": False,
            "canonical_text_created": False,
            "proposition_support_evaluated": False,
            "authority_evaluated": False,
            "semantic_promotion_performed": False,
        }
    else:
        body = _load_verified_artifact(receipt, artifact_store_dir=artifact_store_dir)
        content_type = _text(receipt.get("content_type"))
        media_kind = _media_kind(body, content_type)
        provenance = {
            "source_fetch_receipt_ref": source_receipt_ref,
            "source_content_digest": source_digest,
            "source_url": _text(receipt.get("url")),
            "source_final_url": _text(receipt.get("final_url")),
            "source_content_type": content_type,
        }
        warnings: list[str] = []
        page_count = 0

        if media_kind == "pdf":
            pages = _pdf_page_records(body)
            page_count = len(pages)
            adapter = PdfPageMediaAdapter(
                source_artifact_ref=source_digest,
                provenance=provenance,
            )
            canonical = adapter.adapt(pages)
        elif media_kind == "html":
            html, charset, replacement_used = _decode_html(body, content_type)
            if replacement_used:
                warnings.append("html_decode_used_utf8_replacement")
            adapter = HtmlDocumentMediaAdapter(
                source_artifact_ref=source_digest,
                provenance={**provenance, "decoded_charset": charset},
            )
            canonical = adapter.adapt(html)
        else:
            payload_without_ref = {
                "schema_version": SOURCE_MEDIA_MATERIALIZATION_SCHEMA_VERSION,
                "source_fetch_receipt_ref": source_receipt_ref,
                "source_content_digest": source_digest,
                "state": "blocked_unsupported_media",
                "media_kind": media_kind,
                "source_bytes_reverified": True,
                "canonical_text_created": False,
                "proposition_support_evaluated": False,
                "authority_evaluated": False,
                "semantic_promotion_performed": False,
            }
            payload = dict(payload_without_ref)
            payload["materialization_ref"] = (
                "nat-source-media-materialization:"
                + canonical_sha256(payload_without_ref)
            )
            return payload

        parsed = parse_canonical_text(
            canonical,
            parse_profile="nat_source_evidence_v0_1",
            include_structure_graph=False,
            ingest_receipt={
                "source_fetch_receipt_ref": source_receipt_ref,
                "source_content_digest": source_digest,
                "source_bytes_reverified": True,
            },
        )
        canonical_payload = canonical.to_dict()
        canonical_digest, canonical_relpath = _persist_canonical_json(
            canonical_payload,
            materialized_store_dir=materialized_store_dir,
        )
        payload_without_ref = {
            "schema_version": SOURCE_MEDIA_MATERIALIZATION_SCHEMA_VERSION,
            "source_fetch_receipt_ref": source_receipt_ref,
            "source_content_digest": source_digest,
            "state": "materialized",
            "media_kind": media_kind,
            "source_bytes_reverified": True,
            "source_byte_count": len(body),
            "page_count": page_count,
            "canonical_text_created": True,
            "canonical_text_id": canonical.text_id,
            "canonical_text_digest": canonical_digest,
            "canonical_text_relpath": canonical_relpath,
            "canonical_char_count": len(canonical.text),
            "canonical_segment_count": len(canonical.segments),
            "parse_profile": parsed.parse_profile,
            "parsed_unit_count": len(parsed.parsed_units),
            "warnings": sorted(set([*canonical.warnings, *warnings])),
            "proposition_support_evaluated": False,
            "authority_evaluated": False,
            "semantic_promotion_performed": False,
        }

    payload = dict(payload_without_ref)
    payload["materialization_ref"] = (
        "nat-source-media-materialization:" + canonical_sha256(payload_without_ref)
    )
    return payload


def materialize_source_fetch_dispatch(
    source_dispatch: Mapping[str, Any],
    *,
    artifact_store_dir: str | Path,
    materialized_store_dir: str | Path,
) -> dict[str, Any]:
    receipts = [
        receipt
        for receipt in _sequence(source_dispatch.get("fetch_receipts"))
        if isinstance(receipt, Mapping)
    ]
    receipts.sort(key=lambda item: _text(item.get("receipt_ref")))
    materializations = [
        materialize_source_fetch_receipt(
            receipt,
            artifact_store_dir=artifact_store_dir,
            materialized_store_dir=materialized_store_dir,
        )
        for receipt in receipts
    ]
    materializations.sort(key=lambda item: _text(item.get("materialization_ref")))
    state_counts = Counter(_text(item.get("state")) for item in materializations)
    payload_without_ref = {
        "schema_version": SOURCE_MEDIA_DISPATCH_SCHEMA_VERSION,
        "source_fetch_dispatch_ref": _text(source_dispatch.get("dispatch_ref")),
        "source_fetch_receipt_count": len(receipts),
        "materialization_count": len(materializations),
        "materializations": materializations,
        "counts_by_materialization_state": dict(sorted(state_counts.items())),
        "materialized_source_count": sum(
            1 for item in materializations if item.get("state") == "materialized"
        ),
        "canonical_char_count": sum(
            int(item.get("canonical_char_count", 0) or 0) for item in materializations
        ),
        "proposition_support_evaluated": False,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["dispatch_ref"] = "nat-source-media-dispatch:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = [
    "SOURCE_MEDIA_DISPATCH_SCHEMA_VERSION",
    "SOURCE_MEDIA_MATERIALIZATION_SCHEMA_VERSION",
    "materialize_source_fetch_dispatch",
    "materialize_source_fetch_receipt",
]
