#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology.wikidata import (  # noqa: E402
    ENTITY_EXPORT_TEMPLATE,
    MEDIAWIKI_API_ENDPOINT,
    REQUEST_HEADERS,
    build_slice_from_entity_exports,
    build_wikidata_migration_pack,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize a bounded revision-locked Wikidata migration pack."
    )
    parser.add_argument("--qid", action="append", required=True, help="Repeatable Wikidata QID.")
    parser.add_argument("--source-property", required=True, help="Source property PID.")
    parser.add_argument("--target-property", required=True, help="Target property PID.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for raw entity exports, slice, and migration pack.",
    )
    parser.add_argument(
        "--revision-limit",
        type=int,
        default=2,
        help="Recent revision count to inspect per QID; the newest two are used.",
    )
    parser.add_argument(
        "--query-timeout",
        type=int,
        default=60,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--e0",
        type=int,
        default=1,
        help="Evidence threshold for admissible rank projection.",
    )
    return parser.parse_args()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _fetch_json(url: str, *, params: dict[str, object] | None = None, timeout_seconds: int) -> dict:
    response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    return payload


def _fetch_recent_revisions(qid: str, *, revision_limit: int, timeout_seconds: int) -> list[dict[str, object]]:
    payload = _fetch_json(
        MEDIAWIKI_API_ENDPOINT,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": qid,
            "rvlimit": max(2, int(revision_limit)),
            "rvprop": "ids|timestamp",
            "format": "json",
        },
        timeout_seconds=timeout_seconds,
    )
    pages = payload.get("query", {}).get("pages", {})
    if not isinstance(pages, dict) or not pages:
        return []
    page = next(iter(pages.values()))
    revisions = page.get("revisions", [])
    if not isinstance(revisions, list):
        return []
    return [
        {"revid": int(item["revid"]), "timestamp": str(item["timestamp"])}
        for item in revisions
        if isinstance(item, dict) and "revid" in item and "timestamp" in item
    ]


def _fetch_entity_export(qid: str, revid: int, *, timeout_seconds: int) -> dict:
    payload = _fetch_json(
        ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=revid),
        timeout_seconds=timeout_seconds,
    )
    payload["_source_qid"] = qid
    payload["_source_revision"] = revid
    return payload


def main() -> None:
    args = _parse_args()
    qids = tuple(dict.fromkeys(args.qid))
    out_dir = args.out_dir
    raw_dir = out_dir / "entity_exports"
    raw_dir.mkdir(parents=True, exist_ok=True)

    older_payloads: list[dict] = []
    newer_payloads: list[dict] = []
    revision_manifest: list[dict[str, object]] = []

    for qid in qids:
        revisions = _fetch_recent_revisions(
            qid,
            revision_limit=args.revision_limit,
            timeout_seconds=args.query_timeout,
        )
        if len(revisions) < 2:
            raise SystemExit(f"{qid} returned fewer than two revisions")
        newer = revisions[0]
        older = revisions[1]
        older_payload = _fetch_entity_export(qid, int(older["revid"]), timeout_seconds=args.query_timeout)
        newer_payload = _fetch_entity_export(qid, int(newer["revid"]), timeout_seconds=args.query_timeout)

        older_path = raw_dir / f"{qid.lower()}_t1_{older['revid']}.json"
        newer_path = raw_dir / f"{qid.lower()}_t2_{newer['revid']}.json"
        older_payload["_source_path"] = str(older_path)
        newer_payload["_source_path"] = str(newer_path)
        _write_json(older_path, older_payload)
        _write_json(newer_path, newer_payload)

        older_payloads.append(older_payload)
        newer_payloads.append(newer_payload)
        revision_manifest.append(
            {
                "qid": qid,
                "older_revision": older,
                "newer_revision": newer,
                "older_entity_export": str(older_path),
                "newer_entity_export": str(newer_path),
            }
        )

    slice_payload = build_slice_from_entity_exports(
        {"t1_previous": older_payloads, "t2_current": newer_payloads},
        property_filter=(args.source_property,),
    )
    migration_pack = build_wikidata_migration_pack(
        slice_payload,
        source_property=args.source_property,
        target_property=args.target_property,
        e0=args.e0,
    )

    slice_path = out_dir / "slice.json"
    pack_path = out_dir / "migration_pack.json"
    manifest_path = out_dir / "manifest.json"
    _write_json(slice_path, slice_payload)
    _write_json(pack_path, migration_pack)
    _write_json(
        manifest_path,
        {
            "schema_version": "sl.wikidata_migration_pack.materialization.v0",
            "qids": list(qids),
            "source_property": args.source_property,
            "target_property": args.target_property,
            "revision_pairs": revision_manifest,
            "slice": str(slice_path),
            "migration_pack": str(pack_path),
            "summary": migration_pack["summary"],
        },
    )

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "manifest": str(manifest_path),
                "slice": str(slice_path),
                "migration_pack": str(pack_path),
                "candidate_count": migration_pack["summary"]["candidate_count"],
                "checked_safe_subset_count": len(migration_pack["summary"]["checked_safe_subset"]),
                "requires_review_count": migration_pack["summary"]["requires_review_count"],
                "counts_by_bucket": migration_pack["summary"]["counts_by_bucket"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
