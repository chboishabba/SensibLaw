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
    SPARQL_ENDPOINT,
    attach_wikidata_phi_text_bridge_from_revision_locked_climate_text,
    build_slice_from_entity_exports,
    build_wikidata_migration_pack,
    export_migration_pack_openrefine_csv,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize a bounded revision-locked Wikidata migration pack."
    )
    parser.add_argument("--qid", action="append", help="Repeatable Wikidata QID.")
    parser.add_argument(
        "--qid-file",
        type=Path,
        help="Optional text or JSON file containing QIDs.",
    )
    parser.add_argument(
        "--discover-qids",
        action="store_true",
        help="Discover a bounded live QID sample from the source property.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=10,
        help="Maximum discovered QIDs to use when --discover-qids is enabled.",
    )
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
    parser.add_argument(
        "--openrefine-csv",
        type=Path,
        help="Optional path to also write a flat OpenRefine review CSV.",
    )
    parser.add_argument(
        "--climate-text-source",
        type=Path,
        help="Optional revision-locked climate text-source JSON to emit Observation/Claim rows and bridge into the migration pack.",
    )
    parser.add_argument(
        "--climate-observation-claim-output",
        type=Path,
        help="Optional path to write the derived sl.observation_claim.contract.v1 payload when --climate-text-source is used.",
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


def _extract_qid(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def _load_qids_from_file(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError(f"{path} must contain a JSON array when using JSON mode")
        return [str(item).strip() for item in payload if str(item).strip()]
    qids: list[str] = []
    for line in raw.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        qids.extend(part for part in cleaned.replace(",", " ").split() if part)
    return qids


def _discover_qid_rows(
    *,
    source_property: str,
    candidate_limit: int,
    timeout_seconds: int,
) -> list[dict[str, object]]:
    query = f"""
SELECT ?item ?itemLabel
       (COUNT(DISTINCT ?statement) AS ?statementCount)
       (COUNT(DISTINCT ?qualifier_pid) AS ?qualifierCount)
WHERE {{
  ?item p:{source_property} ?statement .
  OPTIONAL {{
    ?statement ?pq ?qv .
    FILTER(STRSTARTS(STR(?pq), "http://www.wikidata.org/prop/qualifier/"))
    BIND(STRAFTER(STR(?pq), "http://www.wikidata.org/prop/qualifier/") AS ?qualifier_pid)
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?item ?itemLabel
ORDER BY DESC(?qualifierCount) DESC(?statementCount) ?item
LIMIT {max(1, int(candidate_limit))}
""".strip()
    payload = _fetch_json(
        SPARQL_ENDPOINT,
        params={"format": "json", "query": query},
        timeout_seconds=timeout_seconds,
    )
    bindings = payload.get("results", {}).get("bindings", [])
    if not isinstance(bindings, list):
        return []
    rows: list[dict[str, object]] = []
    for row in bindings:
        if not isinstance(row, dict):
            continue
        item_uri = row.get("item", {}).get("value")
        if not item_uri:
            continue
        rows.append(
            {
                "qid": _extract_qid(str(item_uri)),
                "label": str(row.get("itemLabel", {}).get("value") or _extract_qid(str(item_uri))),
                "statement_count": int(row.get("statementCount", {}).get("value") or 0),
                "qualifier_count": int(row.get("qualifierCount", {}).get("value") or 0),
                "source": "discovered",
            }
        )
    return rows


def _resolve_qid_rows(args: argparse.Namespace) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for qid in args.qid or []:
        cleaned = str(qid).strip()
        if cleaned:
            rows.append({"qid": cleaned, "label": cleaned, "source": "explicit"})
    if args.qid_file:
        for qid in _load_qids_from_file(args.qid_file):
            rows.append({"qid": qid, "label": qid, "source": "file"})
    if args.discover_qids:
        rows.extend(
            _discover_qid_rows(
                source_property=args.source_property,
                candidate_limit=args.candidate_limit,
                timeout_seconds=args.query_timeout,
            )
        )
    deduped: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        qid = str(row["qid"])
        if qid in seen:
            continue
        deduped.append(row)
        seen.add(qid)
    return deduped


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
    qid_rows = _resolve_qid_rows(args)
    if not qid_rows:
        raise SystemExit("provide --qid, --qid-file, and/or --discover-qids")
    qids = tuple(str(row["qid"]) for row in qid_rows)
    out_dir = args.out_dir
    raw_dir = out_dir / "entity_exports"
    raw_dir.mkdir(parents=True, exist_ok=True)

    older_payloads: list[dict] = []
    newer_payloads: list[dict] = []
    revision_manifest: list[dict[str, object]] = []

    row_by_qid = {str(row["qid"]): row for row in qid_rows}
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
                "label": row_by_qid.get(qid, {}).get("label", qid),
                "qid_source": row_by_qid.get(qid, {}).get("source", "unknown"),
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
    observation_claim_report_path = None
    if args.climate_text_source:
        climate_text_payload = json.loads(args.climate_text_source.read_text(encoding="utf-8"))
        migration_pack, observation_claim_payload = attach_wikidata_phi_text_bridge_from_revision_locked_climate_text(
            migration_pack,
            climate_text_payload=climate_text_payload,
        )
        observation_claim_report_path = (
            args.climate_observation_claim_output
            if args.climate_observation_claim_output
            else out_dir / "climate_observation_claim.json"
        )
        _write_json(observation_claim_report_path, observation_claim_payload)

    slice_path = out_dir / "slice.json"
    pack_path = out_dir / "migration_pack.json"
    manifest_path = out_dir / "manifest.json"
    _write_json(slice_path, slice_payload)
    _write_json(pack_path, migration_pack)
    openrefine_report = None
    if args.openrefine_csv:
        openrefine_report = export_migration_pack_openrefine_csv(
            migration_pack,
            output_path=str(args.openrefine_csv),
        )
    _write_json(
        manifest_path,
        {
            "schema_version": "sl.wikidata_migration_pack.materialization.v0",
            "qids": list(qids),
            "qid_rows": qid_rows,
            "source_property": args.source_property,
            "target_property": args.target_property,
            "revision_pairs": revision_manifest,
            "slice": str(slice_path),
            "migration_pack": str(pack_path),
            "summary": migration_pack["summary"],
            "openrefine_csv": str(args.openrefine_csv) if args.openrefine_csv else None,
            "climate_text_source": str(args.climate_text_source) if args.climate_text_source else None,
            "climate_observation_claim": str(observation_claim_report_path) if observation_claim_report_path else None,
        },
    )

    output = {
        "out_dir": str(out_dir),
        "manifest": str(manifest_path),
        "slice": str(slice_path),
        "migration_pack": str(pack_path),
        "qids": list(qids),
        "candidate_count": migration_pack["summary"]["candidate_count"],
        "checked_safe_subset_count": len(migration_pack["summary"]["checked_safe_subset"]),
        "requires_review_count": migration_pack["summary"]["requires_review_count"],
        "counts_by_bucket": migration_pack["summary"]["counts_by_bucket"],
    }
    if openrefine_report is not None:
        output["openrefine_csv"] = openrefine_report["output"]
        output["openrefine_row_count"] = openrefine_report["row_count"]
    if observation_claim_report_path is not None:
        output["climate_observation_claim"] = str(observation_claim_report_path)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
