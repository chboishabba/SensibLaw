from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


def receipt_pair(kind: str, value: str) -> tuple[str, str]:
    return (str(kind), str(value))


def receipt_dict(kind: str, value: str) -> dict[str, str]:
    return {"kind": str(kind), "value": str(value)}


def receipt_rows(pairs: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    return [receipt_dict(kind, value) for kind, value in pairs]


def packet_header(
    *,
    version: str,
    summary: str,
    primary_count: int,
    source_family: str | None = None,
    route_target: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    header: dict[str, Any] = {
        "version": str(version),
        "summary": str(summary),
        "primary_count": int(primary_count),
    }
    if source_family:
        header["source_family"] = str(source_family)
    if route_target:
        header["route_target"] = str(route_target)
    if extra:
        header.update(dict(extra))
    return header


def ensure_receipt_kinds(receipts: Sequence[Mapping[str, Any]], *, required_kinds: Iterable[str]) -> None:
    required = {str(kind) for kind in required_kinds if str(kind).strip()}
    present = {str(receipt.get("kind") or "") for receipt in receipts if isinstance(receipt, Mapping)}
    missing = required - present
    if missing:
        raise ValueError(f"missing provenance receipt kinds: {', '.join(sorted(missing))}")
