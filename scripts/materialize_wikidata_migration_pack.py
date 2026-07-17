#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import os
import random
import shlex
import sys
import time
from dataclasses import dataclass, field
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
    build_wikidata_split_plan,
    export_migration_pack_openrefine_csv,
)
from src.policy.residual_profiles import build_typed_residual_profile  # noqa: E402
from src.policy.residual_graph import build_typed_residual_graph  # noqa: E402
from src.policy.climate_ghg_transformation_profile import (  # noqa: E402
    build_coverage_report,
    build_h4_collision_report,
)
from src.policy.review_packet_projection import (  # noqa: E402
    build_review_packet_projection,
)
from scripts.cli_runtime import build_progress_callback  # noqa: E402


_REQUEST_DELAY_SECONDS = 0.5
_REQUEST_RETRY_ATTEMPTS = 4


@dataclass
class _ServiceGovernor:
    baseline_seconds: float
    effective_seconds: float
    last_request_at: float = 0.0
    clean_since: float = field(default_factory=time.monotonic)
    request_count: int = 0
    response_counts: dict[str, int] = field(default_factory=dict)
    retry_count: int = 0
    retry_after_seconds_total: float = 0.0
    minimum_effective_seconds: float = 0.0
    maximum_effective_seconds: float = 0.0

    def __post_init__(self) -> None:
        self.minimum_effective_seconds = self.effective_seconds
        self.maximum_effective_seconds = self.effective_seconds


class _WikidataTransport:
    """Polite shared session with independent pressure histories per service."""

    def __init__(self, *, baseline_seconds: float, retries: int) -> None:
        self.session = requests.Session()
        self.retries = retries
        self.governors = {
            name: _ServiceGovernor(baseline_seconds, baseline_seconds)
            for name in ("wdqs", "action_api", "entity_export")
        }
        self.contact_identity_present = bool(
            os.getenv("SENSIBLAW_WIKIDATA_CONTACT_NAME", "").strip()
            or os.getenv("SENSIBLAW_WIKIDATA_CONTACT_EMAIL", "").strip()
        )
        contact = " ".join(
            value
            for value in (
                os.getenv("SENSIBLAW_WIKIDATA_CONTACT_NAME", "").strip(),
                os.getenv("SENSIBLAW_WIKIDATA_CONTACT_EMAIL", "").strip(),
            )
            if value
        )
        agent = "SensibLaw-Wikidata-QualifierDrift/0.1 (https://github.com/chboishabba/SensibLaw"
        self.headers = {
            **REQUEST_HEADERS,
            "User-Agent": agent + (f"; {contact})" if contact else ")"),
        }
        token = os.getenv("SENSIBLAW_WIKIDATA_OAUTH_ACCESS_TOKEN", "").strip()
        self.authentication_mode = "oauth2" if token else "anonymous"
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(self.headers)
        self.resumed_export_count = 0
        self.downloaded_export_count = 0

    def fetch_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None,
        timeout_seconds: int,
        service: str,
    ) -> dict:
        governor = self.governors[service]
        for attempt in range(max(1, self.retries)):
            elapsed = time.monotonic() - governor.last_request_at
            if elapsed < governor.effective_seconds:
                time.sleep(governor.effective_seconds - elapsed)
            response = self.session.get(url, params=params, timeout=timeout_seconds)
            governor.last_request_at = time.monotonic()
            governor.request_count += 1
            governor.response_counts[str(response.status_code)] = (
                governor.response_counts.get(str(response.status_code), 0) + 1
            )
            if response.status_code not in {429, 502, 503, 504}:
                response.raise_for_status()
                if time.monotonic() - governor.clean_since >= 600:
                    governor.effective_seconds = max(
                        governor.baseline_seconds, governor.effective_seconds * 0.9
                    )
                    governor.clean_since = time.monotonic()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError(f"expected JSON object from {url}")
                return payload
            governor.retry_count += 1
            governor.clean_since = time.monotonic()
            raw_retry_after = str(response.headers.get("Retry-After") or "").strip()
            retry_after = (
                float(raw_retry_after)
                if raw_retry_after.replace(".", "", 1).isdigit()
                else 0.0
            )
            wait_seconds = (
                retry_after
                if retry_after > 0
                else max(5.0, governor.effective_seconds * (2 ** (attempt + 1)))
            )
            governor.retry_after_seconds_total += wait_seconds
            governor.effective_seconds = min(
                60.0, max(governor.effective_seconds * 2, wait_seconds)
            )
            governor.minimum_effective_seconds = min(
                governor.minimum_effective_seconds, governor.effective_seconds
            )
            governor.maximum_effective_seconds = max(
                governor.maximum_effective_seconds, governor.effective_seconds
            )
            if attempt + 1 >= max(1, self.retries):
                response.raise_for_status()
            time.sleep(wait_seconds * random.uniform(0.9, 1.1))
        raise RuntimeError(f"bounded request retries exhausted for {url}")

    def receipt(self) -> dict[str, object]:
        return {
            "authentication_mode": self.authentication_mode,
            "contact_identity_present": self.contact_identity_present,
            "resumed_export_count": self.resumed_export_count,
            "downloaded_export_count": self.downloaded_export_count,
            "services": {
                name: {
                    "request_count": item.request_count,
                    "response_counts": item.response_counts,
                    "retry_count": item.retry_count,
                    "retry_after_seconds_total": item.retry_after_seconds_total,
                    "baseline_interval_ms": int(item.baseline_seconds * 1000),
                    "minimum_effective_interval_ms": int(
                        item.minimum_effective_seconds * 1000
                    ),
                    "maximum_effective_interval_ms": int(
                        item.maximum_effective_seconds * 1000
                    ),
                }
                for name, item in self.governors.items()
            },
        }


_TRANSPORT: _WikidataTransport | None = None


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
        "--discover-company-direct",
        action="store_true",
        help=(
            "Discover a bounded statement-level P5991 page whose subjects have "
            "a direct company/business/enterprise P31 and no P14143 statement."
        ),
    )
    parser.add_argument(
        "--discovery-cursor-qid",
        default="",
        help="QID component of the exclusive discovery cursor, for example Q123.",
    )
    parser.add_argument(
        "--discovery-cursor-statement",
        default="",
        help=(
            "Statement-GUID component of the exclusive discovery cursor. "
            "Supply it with --discovery-cursor-qid for lossless pagination."
        ),
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
        "--request-delay-ms",
        type=int,
        default=500,
        help="Minimum delay per live service request (default: 500 ms).",
    )
    parser.add_argument(
        "--request-retries",
        type=int,
        default=4,
        help="Bounded retries for 429/502/503/504 responses (default: 4).",
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
    parser.add_argument(
        "--review-packets-output",
        type=Path,
        help=(
            "Optional path for compact generic review packets for reconciled "
            "split-required candidates."
        ),
    )
    parser.add_argument(
        "--residual-graph-output",
        type=Path,
        help=(
            "Optional path for the generic typed residual graph built from the "
            "same reconciled split-required rows as review packets."
        ),
    )
    parser.add_argument(
        "--rule-coverage-output",
        type=Path,
        help=(
            "Optional candidate-only A1/A2/A3/A5/H4 detector and dry-run coverage "
            "report. This never creates an edit or execution manifest."
        ),
    )
    parser.add_argument(
        "--h4-collision-output",
        type=Path,
        help="Optional path to write the structured H4 collision report.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a matching pinned run-state in --out-dir.",
    )
    parser.add_argument(
        "--progress-output",
        type=Path,
        help="Optional live progress JSON path (default: --out-dir/progress.json).",
    )
    parser.add_argument(
        "--progress-format",
        choices=("human", "json", "bar"),
        default="bar",
        help="Terminal progress format (default: bar; falls back to human outside a TTY).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_false",
        dest="progress_enabled",
        help="Disable terminal progress output; progress.json is still written.",
    )
    parser.set_defaults(progress_enabled=True)
    return parser.parse_args()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _fetch_json(
    url: str, *, params: dict[str, object] | None = None, timeout_seconds: int
) -> dict:
    if _TRANSPORT is None:
        raise RuntimeError("Wikidata transport is not configured")
    service = (
        "wdqs"
        if url == SPARQL_ENDPOINT
        else "action_api"
        if url == MEDIAWIKI_API_ENDPOINT
        else "entity_export"
    )
    request_params = dict(params or {})
    if service == "action_api":
        request_params.setdefault("maxlag", 5)
    return _TRANSPORT.fetch_json(
        url, params=request_params, timeout_seconds=timeout_seconds, service=service
    )


def _extract_qid(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def _canonical_statement_id(value: str) -> str:
    """Normalize a WDQS statement URI suffix to Wikibase's claim GUID form."""

    suffix = _extract_qid(value)
    if "$" in suffix:
        return suffix
    if suffix.startswith("Q") and "-" in suffix:
        qid, guid = suffix.split("-", 1)
        if qid[1:].isdigit() and guid:
            return f"{qid}${guid}"
    return suffix


def _normalize_rank(value: str) -> str:
    suffix = str(value or "").rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    mapping = {
        "PreferredRank": "preferred",
        "NormalRank": "normal",
        "DeprecatedRank": "deprecated",
    }
    return mapping.get(suffix, suffix or "normal")


def _canonical_json_digest(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _company_direct_discovery_query(
    *,
    source_property: str,
    target_property: str,
    cursor_qid: str,
    page_size: int,
    cursor_statement: str = "",
) -> str:
    cursor_filter = ""
    cleaned_cursor = str(cursor_qid or "").strip()
    cleaned_statement = str(cursor_statement or "").strip()
    if cleaned_cursor:
        item_uri = "http://www.wikidata.org/entity/" + cleaned_cursor
        if cleaned_statement:
            statement_suffix = cleaned_statement.replace("$", "-", 1)
            statement_uri = (
                "http://www.wikidata.org/entity/statement/" + statement_suffix
            )
            cursor_filter = (
                f'FILTER(STR(?item) > "{item_uri}" || '
                f'(STR(?item) = "{item_uri}" && '
                f'STR(?statement) > "{statement_uri}"))'
            )
        else:
            cursor_filter = f'FILTER(STR(?item) > "{item_uri}")'
    return f"""
SELECT ?item ?statement ?rank
       (GROUP_CONCAT(DISTINCT STR(?type); separator="|") AS ?types)
WHERE {{
  ?item p:{source_property} ?statement .
  ?statement wikibase:rank ?rank .
  ?item wdt:P31 ?type .
  VALUES ?type {{ wd:Q783794 wd:Q6881511 wd:Q4830453 }}
  FILTER NOT EXISTS {{ ?item wdt:{target_property} ?existingTarget . }}
  {cursor_filter}
}}
GROUP BY ?item ?statement ?rank
ORDER BY ?item ?statement
LIMIT {max(1, int(page_size))}
""".strip()


def _discover_company_direct_statement_rows(
    *,
    source_property: str,
    target_property: str,
    page_size: int,
    cursor_qid: str,
    timeout_seconds: int,
    cursor_statement: str = "",
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Discover a deterministic, non-authoritative statement-level page."""

    query = _company_direct_discovery_query(
        source_property=source_property,
        target_property=target_property,
        cursor_qid=cursor_qid,
        page_size=page_size,
        cursor_statement=cursor_statement,
    )
    payload = _fetch_json(
        SPARQL_ENDPOINT,
        params={"format": "json", "query": query},
        timeout_seconds=timeout_seconds,
    )
    bindings = payload.get("results", {}).get("bindings", [])
    if not isinstance(bindings, list):
        bindings = []

    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        item_uri = binding.get("item", {}).get("value")
        statement_uri = binding.get("statement", {}).get("value")
        if not item_uri or not statement_uri:
            continue
        qid = _extract_qid(str(item_uri))
        statement_id = _canonical_statement_id(str(statement_uri))
        row = grouped.setdefault(
            (qid, statement_id),
            {
                "subject_qid": qid,
                "statement_id": statement_id,
                "rank": _normalize_rank(
                    str(binding.get("rank", {}).get("value") or "normal")
                ),
                "direct_p31": set(),
                "target_property_present_at_discovery": False,
                "stratum": "company_direct",
            },
        )
        type_uris = str(binding.get("types", {}).get("value") or "").split("|")
        legacy_type_uri = binding.get("type", {}).get("value")
        if legacy_type_uri:
            type_uris.append(str(legacy_type_uri))
        direct_p31 = row["direct_p31"]
        if isinstance(direct_p31, set):
            direct_p31.update(
                _extract_qid(type_uri) for type_uri in type_uris if type_uri
            )

    rows: list[dict[str, object]] = []
    for row in grouped.values():
        row["direct_p31"] = sorted(row["direct_p31"])
        rows.append(row)
    rows.sort(key=lambda row: (str(row["subject_qid"]), str(row["statement_id"])))
    next_cursor = (
        {
            "subject_qid": str(rows[-1]["subject_qid"]),
            "statement_id": str(rows[-1]["statement_id"]),
        }
        if rows
        else None
    )
    metadata = {
        "query": query,
        "query_sha256": _canonical_json_digest({"query": query}),
        "response_sha256": _canonical_json_digest(payload),
        "endpoint": SPARQL_ENDPOINT,
        "executed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "ordering": "subject_qid ASC, statement_id ASC",
        "page_size": max(1, int(page_size)),
        "cursor_qid": str(cursor_qid or "").strip() or None,
        "cursor_statement": str(cursor_statement or "").strip() or None,
        "next_cursor": next_cursor,
    }
    return rows, metadata


def _reconcile_discovery_row(
    row: dict[str, object],
    entity_export: dict,
    *,
    source_property: str,
    target_property: str,
) -> dict[str, object]:
    """Check that a discovered GUID survives in one pinned entity export."""

    qid = str(row["subject_qid"])
    entities = entity_export.get("entities")
    entity = entities.get(qid) if isinstance(entities, dict) else None
    if not isinstance(entity, dict):
        return {**row, "reconciliation_status": "entity_revision_unavailable"}
    claims = entity.get("claims")
    if not isinstance(claims, dict):
        return {**row, "reconciliation_status": "entity_revision_unavailable"}
    source_claims = claims.get(source_property)
    if not isinstance(source_claims, list):
        return {**row, "reconciliation_status": "statement_missing"}
    statement_id = str(row["statement_id"])
    matched = next(
        (
            claim
            for claim in source_claims
            if isinstance(claim, dict) and str(claim.get("id") or "") == statement_id
        ),
        None,
    )
    if matched is None:
        return {**row, "reconciliation_status": "statement_changed_since_discovery"}
    return {
        **row,
        "reconciliation_status": "statement_reconciled",
        "entity_revision": int(entity_export.get("_source_revision") or 0) or None,
        "target_property_present_at_reconciliation": bool(claims.get(target_property)),
    }


def _filter_export_to_discovery_rows(
    entity_export: dict,
    rows: list[dict[str, object]],
    *,
    source_property: str,
) -> dict:
    """Retain complete pinned family context for reconciled selected GUIDs.

    The caller later selects emitted candidates by GUID.  Filtering the export
    here would make a partial WDQS page look like a complete statement family.
    """

    del source_property
    reconciled_subjects = {
        str(row["subject_qid"])
        for row in rows
        if row.get("reconciliation_status") == "statement_reconciled"
    }
    filtered = deepcopy(entity_export)
    entities = filtered.get("entities")
    if not isinstance(entities, dict):
        return filtered
    filtered["entities"] = {
        str(qid): entity
        for qid, entity in entities.items()
        if str(qid) in reconciled_subjects
    }
    return filtered


def _profile_context(candidate: dict) -> dict[str, object]:
    """Supply only explicit comparison gates for the generic profile carrier."""

    subject_resolution = candidate.get("subject_resolution")
    resolved_subject = (
        isinstance(subject_resolution, dict)
        and subject_resolution.get("status") == "resolved"
    )
    classification = str(candidate.get("classification") or "")
    return {
        "entity_kind_compatible": resolved_subject,
        "relation_compatible": True,
        "temporal_compatible": classification != "abstain",
        "source_pnf_compatible": True,
        "superclass_compatible": resolved_subject,
        "disjointness_clear": True,
    }


def _build_reconciled_review_packets(
    migration_pack: dict,
    *,
    discovery_rows: list[dict[str, object]],
) -> dict[str, object]:
    """Thin Nat/materializer wrapper over generic profile and packet surfaces."""

    revisions = {
        (str(row.get("subject_qid")), str(row.get("statement_id"))): row
        for row in discovery_rows
        if row.get("reconciliation_status") == "statement_reconciled"
    }
    split_plans = build_wikidata_split_plan(migration_pack).get("plans", [])
    plan_by_candidate = {
        candidate_id: plan
        for plan in split_plans
        if isinstance(plan, dict)
        for candidate_id in plan.get("source_candidate_ids", [])
    }
    packets: list[dict[str, object]] = []
    profiles: list[dict[str, object]] = []
    for candidate in migration_pack.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        statement_id = str(candidate.get("source_statement_id") or "")
        row = revisions.get((str(candidate.get("entity_qid")), statement_id))
        if not row:
            continue
        assessment = candidate.get("domain_pressure_assessment")
        if not isinstance(assessment, dict):
            continue
        revision = row.get("entity_revision")
        if not isinstance(revision, int) or revision <= 0:
            continue
        revision_ref = f"wikidata:{candidate['entity_qid']}@{revision}"
        profile = build_typed_residual_profile(
            assessment=assessment,
            context=_profile_context(candidate),
            source_revision_ref=revision_ref,
            source_anchor_refs=[statement_id],
        )
        profiles.append(profile)
        plan = plan_by_candidate.get(candidate.get("candidate_id"))
        packet = build_review_packet_projection(
            residual_profile=profile,
            candidate_record=candidate,
            source_revision_ref=revision_ref,
            proposed_decomposition=plan if isinstance(plan, dict) else None,
            source_anchor_refs=[statement_id],
        )
        packets.append(packet)
    packets.sort(key=lambda packet: str(packet["candidate_ref"]))
    profiles.sort(key=lambda profile: str(profile["candidate_ref"]))
    return {
        "schema_version": "sl.review_packet_projection_set.v0_1",
        "authority": "review_packet_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
        "packets": packets,
        "residual_profiles": profiles,
        "summary": {"packet_count": len(packets)},
    }


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
                "label": str(
                    row.get("itemLabel", {}).get("value") or _extract_qid(str(item_uri))
                ),
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


def _fetch_recent_revisions(
    qid: str, *, revision_limit: int, timeout_seconds: int
) -> list[dict[str, object]]:
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


def _fetch_recent_revision_map(
    qids: tuple[str, ...],
    *,
    revision_limit: int,
    timeout_seconds: int,
    progress_callback=None,
) -> dict[str, list[dict[str, object]]]:
    """Pin exact recent revisions; the API forbids multi-title rvlimit calls."""

    revision_map: dict[str, list[dict[str, object]]] = {}
    started_at = time.monotonic()
    for index, qid in enumerate(qids, start=1):
        revision_map[qid] = _fetch_recent_revisions(
            qid, revision_limit=revision_limit, timeout_seconds=timeout_seconds
        )
        if progress_callback:
            elapsed_seconds = max(0.001, time.monotonic() - started_at)
            rate = index / elapsed_seconds
            progress_callback(
                "revision_pinning",
                {
                    "section": "revision_pinning",
                    "completed": index,
                    "total": len(qids),
                    "elapsed_seconds": round(elapsed_seconds, 3),
                    "items_per_second": round(rate, 4),
                    "eta_seconds_remaining": round((len(qids) - index) / rate, 3),
                    "message": f"Pinned {qid}.",
                },
            )
    return revision_map


def _read_valid_export(
    path: Path, *, qid: str, revid: int, receipt_path: Path | None = None
) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("_source_qid") != qid or payload.get("_source_revision") != revid:
        return None
    if receipt_path is not None:
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(receipt, dict) or (
            receipt.get("qid") != qid
            or receipt.get("revision") != revid
            or receipt.get("content_sha256") != _canonical_json_digest(payload)
        ):
            return None
    payload["_source_path"] = str(path)
    return payload


def _write_export_receipt(path: Path, *, qid: str, revid: int, payload: dict) -> None:
    _write_json(
        path,
        {
            "schema_version": "sl.wikidata_entity_export_receipt.v1",
            "qid": qid,
            "revision": revid,
            "content_sha256": _canonical_json_digest(payload),
        },
    )


def _write_progress(
    path: Path,
    *,
    phase: str,
    total_exports: int,
    completed_exports: int,
    current_qid: str | None,
    current_revision: int | None,
    started_at: float,
    resume_command: str,
    terminal: bool = False,
) -> None:
    elapsed_seconds = max(0.0, time.monotonic() - started_at)
    throughput = completed_exports / elapsed_seconds if elapsed_seconds else 0.0
    remaining = max(0, total_exports - completed_exports)
    _write_json(
        path,
        {
            "schema_version": "sl.wikidata_migration_pack.progress.v1",
            "phase": phase,
            "terminal": terminal,
            "total_export_count": total_exports,
            "completed_export_count": completed_exports,
            "remaining_export_count": remaining,
            "current_qid": current_qid,
            "current_revision": current_revision,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "exports_per_second": round(throughput, 6),
            "estimated_remaining_seconds": (
                round(remaining / throughput, 3) if throughput else None
            ),
            "safe_resume_command": resume_command,
        },
    )


def _run_contract(args: argparse.Namespace) -> dict[str, object]:
    return {
        "source_property": args.source_property,
        "target_property": args.target_property,
        "discover_company_direct": bool(args.discover_company_direct),
        "discover_qids": bool(args.discover_qids),
        "candidate_limit": args.candidate_limit,
        "revision_limit": args.revision_limit,
        "explicit_qids": list(args.qid or []),
        "qid_file": str(args.qid_file) if args.qid_file else None,
    }


def _fetch_entity_export(qid: str, revid: int, *, timeout_seconds: int) -> dict:
    payload = _fetch_json(
        ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=revid),
        timeout_seconds=timeout_seconds,
    )
    payload["_source_qid"] = qid
    payload["_source_revision"] = revid
    return payload


def main() -> None:
    global _REQUEST_DELAY_SECONDS, _REQUEST_RETRY_ATTEMPTS, _TRANSPORT

    args = _parse_args()
    _REQUEST_DELAY_SECONDS = max(500, int(args.request_delay_ms)) / 1000.0
    _REQUEST_RETRY_ATTEMPTS = max(1, int(args.request_retries))
    _TRANSPORT = _WikidataTransport(
        baseline_seconds=_REQUEST_DELAY_SECONDS, retries=_REQUEST_RETRY_ATTEMPTS
    )
    terminal_progress = build_progress_callback(
        enabled=bool(args.progress_enabled), fmt=args.progress_format
    )
    out_dir = args.out_dir
    state_path = out_dir / "run-state.json"
    contract = _run_contract(args)
    discovery_rows: list[dict[str, object]] = []
    discovery_metadata: dict[str, object] | None = None
    revision_map: dict[str, list[dict[str, object]]]
    if args.resume:
        if not state_path.is_file():
            raise SystemExit(f"--resume requires pinned state: {state_path}")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("contract") != contract:
            raise SystemExit("--resume contract differs from pinned run-state")
        qid_rows = state.get("qid_rows")
        revision_map = state.get("revision_map")
        discovery_rows = state.get("discovery_rows") or []
        discovery_metadata = state.get("discovery_metadata")
        if not isinstance(qid_rows, list) or not isinstance(revision_map, dict):
            raise SystemExit("run-state is incomplete or corrupt")
    elif args.discover_company_direct:
        discovery_rows, discovery_metadata = _discover_company_direct_statement_rows(
            source_property=args.source_property,
            target_property=args.target_property,
            page_size=args.candidate_limit,
            cursor_qid=args.discovery_cursor_qid,
            timeout_seconds=args.query_timeout,
            cursor_statement=args.discovery_cursor_statement,
        )
        qid_rows = [
            {
                "qid": str(row["subject_qid"]),
                "label": str(row["subject_qid"]),
                "source": "company_direct_discovery",
            }
            for row in discovery_rows
        ]
        deduped_qids: list[dict[str, object]] = []
        seen_qids: set[str] = set()
        for row in qid_rows:
            if str(row["qid"]) in seen_qids:
                continue
            deduped_qids.append(row)
            seen_qids.add(str(row["qid"]))
        qid_rows = deduped_qids
    else:
        qid_rows = _resolve_qid_rows(args)
    if not qid_rows:
        raise SystemExit(
            "provide --qid, --qid-file, --discover-qids, and/or --discover-company-direct"
        )
    qids = tuple(str(row["qid"]) for row in qid_rows)
    raw_dir = out_dir / "entity_exports"
    receipt_dir = out_dir / "export-receipts"
    progress_path = args.progress_output or out_dir / "progress.json"
    resume_args = list(sys.argv)
    if "--resume" not in resume_args:
        resume_args.append("--resume")
    resume_command = shlex.join([sys.executable, *resume_args])
    phase_started_at = time.monotonic()
    total_exports = len(qids) * (1 if args.discover_company_direct else 2)
    completed_exports = 0
    raw_dir.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        revision_map = _fetch_recent_revision_map(
            qids,
            revision_limit=args.revision_limit,
            timeout_seconds=args.query_timeout,
            progress_callback=terminal_progress,
        )
        missing = [
            qid
            for qid in qids
            if len(revision_map.get(qid, []))
            < (1 if args.discover_company_direct else 2)
        ]
        if missing:
            raise SystemExit(
                f"unable to pin required revisions: {', '.join(missing[:5])}"
            )
        _write_json(
            state_path,
            {
                "run_state_schema": "sl.wikidata_migration_pack.run_state.v1",
                "contract": contract,
                "query_contract_hash": _canonical_json_digest(contract),
                "population_cursor_start": args.discovery_cursor_qid or None,
                "population_cursor_end": (discovery_metadata or {}).get("next_cursor"),
                "population_exhausted": (
                    not args.discover_company_direct
                    or len(discovery_rows) < max(1, int(args.candidate_limit))
                ),
                "ordered_qids": list(qids),
                "qid_rows": qid_rows,
                "discovery_rows": discovery_rows,
                "discovery_metadata": discovery_metadata,
                "revision_map": revision_map,
                "transport_policy_version": "service_governors.v1",
                "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
        )
    _write_progress(
        progress_path,
        phase="exporting",
        total_exports=total_exports,
        completed_exports=completed_exports,
        current_qid=None,
        current_revision=None,
        started_at=phase_started_at,
        resume_command=resume_command,
    )
    if terminal_progress:
        terminal_progress(
            "exports_started",
            {
                "section": "entity_exports",
                "completed": completed_exports,
                "total": total_exports,
                "message": "Revision pinning complete; acquiring exports.",
            },
        )

    older_payloads: list[dict] = []
    newer_payloads: list[dict] = []
    revision_manifest: list[dict[str, object]] = []
    current_exports_by_qid: dict[str, dict] = {}

    row_by_qid = {str(row["qid"]): row for row in qid_rows}
    for qid in qids:
        revisions = revision_map.get(qid, [])
        if len(revisions) < (1 if args.discover_company_direct else 2):
            raise SystemExit(f"{qid} returned fewer than two revisions")
        newer = revisions[0]
        newer_path = raw_dir / f"{qid.lower()}_t2_{newer['revid']}.json"
        newer_receipt_path = (
            receipt_dir / f"{qid.lower()}__revid-{newer['revid']}.receipt.json"
        )
        newer_payload = _read_valid_export(
            newer_path,
            qid=qid,
            revid=int(newer["revid"]),
            receipt_path=newer_receipt_path,
        )
        if newer_payload is None:
            newer_payload = _fetch_entity_export(
                qid, int(newer["revid"]), timeout_seconds=args.query_timeout
            )
            newer_payload["_source_path"] = str(newer_path)
            _write_json(newer_path, newer_payload)
            if _TRANSPORT is not None:
                _TRANSPORT.downloaded_export_count += 1
        elif _TRANSPORT is not None:
            _TRANSPORT.resumed_export_count += 1
        _write_export_receipt(
            newer_receipt_path,
            qid=qid,
            revid=int(newer["revid"]),
            payload=newer_payload,
        )
        completed_exports += 1
        _write_progress(
            progress_path,
            phase="exporting",
            total_exports=total_exports,
            completed_exports=completed_exports,
            current_qid=qid,
            current_revision=int(newer["revid"]),
            started_at=phase_started_at,
            resume_command=resume_command,
        )
        if terminal_progress:
            elapsed_seconds = max(0.001, time.monotonic() - phase_started_at)
            terminal_progress(
                "entity_export",
                {
                    "section": "entity_exports",
                    "completed": completed_exports,
                    "total": total_exports,
                    "elapsed_seconds": round(elapsed_seconds, 3),
                    "items_per_second": round(completed_exports / elapsed_seconds, 4),
                    "eta_seconds_remaining": round(
                        (total_exports - completed_exports)
                        / (completed_exports / elapsed_seconds),
                        3,
                    ),
                    "message": f"Validated {qid}@{newer['revid']}.",
                },
            )
        newer_payloads.append(newer_payload)
        current_exports_by_qid[qid] = newer_payload
        older = revisions[1] if len(revisions) >= 2 else None
        older_payload = None
        older_path = None
        if older is not None and not args.discover_company_direct:
            older_path = raw_dir / f"{qid.lower()}_t1_{older['revid']}.json"
            older_receipt_path = (
                receipt_dir / f"{qid.lower()}__revid-{older['revid']}.receipt.json"
            )
            older_payload = _read_valid_export(
                older_path,
                qid=qid,
                revid=int(older["revid"]),
                receipt_path=older_receipt_path,
            )
            if older_payload is None:
                older_payload = _fetch_entity_export(
                    qid, int(older["revid"]), timeout_seconds=args.query_timeout
                )
                older_payload["_source_path"] = str(older_path)
                _write_json(older_path, older_payload)
                if _TRANSPORT is not None:
                    _TRANSPORT.downloaded_export_count += 1
            elif _TRANSPORT is not None:
                _TRANSPORT.resumed_export_count += 1
            _write_export_receipt(
                older_receipt_path,
                qid=qid,
                revid=int(older["revid"]),
                payload=older_payload,
            )
            completed_exports += 1
            _write_progress(
                progress_path,
                phase="exporting",
                total_exports=total_exports,
                completed_exports=completed_exports,
                current_qid=qid,
                current_revision=int(older["revid"]),
                started_at=phase_started_at,
                resume_command=resume_command,
            )
            if terminal_progress:
                elapsed_seconds = max(0.001, time.monotonic() - phase_started_at)
                terminal_progress(
                    "entity_export",
                    {
                        "section": "entity_exports",
                        "completed": completed_exports,
                        "total": total_exports,
                        "elapsed_seconds": round(elapsed_seconds, 3),
                        "items_per_second": round(
                            completed_exports / elapsed_seconds, 4
                        ),
                        "eta_seconds_remaining": round(
                            (total_exports - completed_exports)
                            / (completed_exports / elapsed_seconds),
                            3,
                        ),
                        "message": f"Validated {qid}@{older['revid']}.",
                    },
                )
            older_payloads.append(older_payload)
        revision_manifest.append(
            {
                "qid": qid,
                "label": row_by_qid.get(qid, {}).get("label", qid),
                "qid_source": row_by_qid.get(qid, {}).get("source", "unknown"),
                "older_revision": older,
                "newer_revision": newer,
                "older_entity_export": str(older_path) if older_path else None,
                "newer_entity_export": str(newer_path),
            }
        )

    if args.discover_company_direct:
        discovery_rows = [
            _reconcile_discovery_row(
                row,
                current_exports_by_qid[str(row["subject_qid"])],
                source_property=args.source_property,
                target_property=args.target_property,
            )
            for row in discovery_rows
        ]
        newer_payloads = [
            _filter_export_to_discovery_rows(
                current_exports_by_qid[qid],
                [row for row in discovery_rows if str(row["subject_qid"]) == qid],
                source_property=args.source_property,
            )
            for qid in qids
        ]

    slice_payload = build_slice_from_entity_exports(
        (
            {"t2_current": newer_payloads}
            if args.discover_company_direct
            else {"t1_previous": older_payloads, "t2_current": newer_payloads}
        ),
        property_filter=(args.source_property, "P31", args.target_property),
    )
    migration_pack = build_wikidata_migration_pack(
        slice_payload,
        source_property=args.source_property,
        target_property=args.target_property,
        e0=args.e0,
        selected_statement_ids=(
            [
                str(row["statement_id"])
                for row in discovery_rows
                if row.get("reconciliation_status") == "statement_reconciled"
            ]
            if args.discover_company_direct
            else None
        ),
    )

    family_member_pack = None
    if (args.discover_company_direct or args.qid) and (
        args.rule_coverage_output or args.h4_collision_output
    ):
        # Keep the selected discovery population narrow while supplying every
        # sibling GUID from each pinned entity to the generic family-evidence
        # carrier. This is diagnostic hydration only, never an edit population.
        family_member_pack = build_wikidata_migration_pack(
            slice_payload,
            source_property=args.source_property,
            target_property=args.target_property,
            e0=args.e0,
        )

    rule_coverage = None
    if args.rule_coverage_output:
        query_hash = str((discovery_metadata or {}).get("query_sha256") or "").strip()
        source_snapshot_ref = (
            f"wdqs-query:{query_hash}"
            if query_hash
            else "wikibase-migration-pack:"
            + hashlib.sha256(
                json.dumps(
                    revision_manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        )
        rule_coverage = build_coverage_report(
            migration_pack,
            source_snapshot_ref=source_snapshot_ref,
            target_collision_state=(
                "absent" if args.discover_company_direct else "unknown"
            ),
            family_member_candidates=(
                family_member_pack.get("candidates", [])
                if family_member_pack is not None
                else None
            ),
        )
        _write_json(args.rule_coverage_output, rule_coverage)

    h4_collision_report = None
    if args.h4_collision_output:
        h4_collision_report = build_h4_collision_report(
            migration_pack,
            family_member_candidates=(
                family_member_pack.get("candidates", [])
                if family_member_pack is not None
                else None
            ),
        )
        _write_json(args.h4_collision_output, h4_collision_report)

    review_packet_set = None
    residual_graph = None
    if args.review_packets_output or args.residual_graph_output:
        review_packet_set = _build_reconciled_review_packets(
            migration_pack,
            discovery_rows=discovery_rows,
        )
        if args.review_packets_output:
            _write_json(args.review_packets_output, review_packet_set)
        if args.residual_graph_output:
            residual_graph = build_typed_residual_graph(
                review_packet_set["residual_profiles"]
            )
            _write_json(args.residual_graph_output, residual_graph)
    observation_claim_report_path = None
    if args.climate_text_source:
        climate_text_payload = json.loads(
            args.climate_text_source.read_text(encoding="utf-8")
        )
        migration_pack, observation_claim_payload = (
            attach_wikidata_phi_text_bridge_from_revision_locked_climate_text(
                migration_pack,
                climate_text_payload=climate_text_payload,
            )
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
            "discovery": (
                {
                    "schema_version": "sl.wikibase_statement_discovery_manifest.v0_1",
                    "stratum": "company_direct",
                    "authority": "discovery_only",
                    "promotion_effect": "not_evaluated",
                    "metadata": discovery_metadata,
                    "rows": discovery_rows,
                    "summary": {
                        "discovered_statement_count": len(discovery_rows),
                        "reconciled_statement_count": sum(
                            row.get("reconciliation_status") == "statement_reconciled"
                            for row in discovery_rows
                        ),
                    },
                }
                if args.discover_company_direct
                else None
            ),
            "revision_pairs": revision_manifest,
            "slice": str(slice_path),
            "migration_pack": str(pack_path),
            "summary": migration_pack["summary"],
            "openrefine_csv": str(args.openrefine_csv) if args.openrefine_csv else None,
            "review_packets": str(args.review_packets_output)
            if args.review_packets_output
            else None,
            "residual_graph": str(args.residual_graph_output)
            if args.residual_graph_output
            else None,
            "rule_coverage": str(args.rule_coverage_output)
            if args.rule_coverage_output
            else None,
            "h4_collision_report": str(args.h4_collision_output)
            if args.h4_collision_output
            else None,
            "climate_text_source": str(args.climate_text_source)
            if args.climate_text_source
            else None,
            "climate_observation_claim": str(observation_claim_report_path)
            if observation_claim_report_path
            else None,
            "run_state": str(state_path),
            "transport": _TRANSPORT.receipt() if _TRANSPORT is not None else None,
        },
    )
    _write_progress(
        progress_path,
        phase="completed",
        total_exports=total_exports,
        completed_exports=completed_exports,
        current_qid=None,
        current_revision=None,
        started_at=phase_started_at,
        resume_command=resume_command,
        terminal=True,
    )

    output = {
        "out_dir": str(out_dir),
        "manifest": str(manifest_path),
        "slice": str(slice_path),
        "migration_pack": str(pack_path),
        "qids": list(qids),
        "candidate_count": migration_pack["summary"]["candidate_count"],
        "checked_safe_subset_count": len(
            migration_pack["summary"]["checked_safe_subset"]
        ),
        "requires_review_count": migration_pack["summary"]["requires_review_count"],
        "counts_by_bucket": migration_pack["summary"]["counts_by_bucket"],
    }
    if openrefine_report is not None:
        output["openrefine_csv"] = openrefine_report["output"]
        output["openrefine_row_count"] = openrefine_report["row_count"]
    if review_packet_set is not None:
        if args.review_packets_output:
            output["review_packets"] = str(args.review_packets_output)
        output["review_packet_count"] = review_packet_set["summary"]["packet_count"]
    if residual_graph is not None:
        output["residual_graph"] = str(args.residual_graph_output)
        output["residual_graph_edge_count"] = residual_graph["summary"]["edge_count"]
    if rule_coverage is not None:
        output["rule_coverage"] = str(args.rule_coverage_output)
        output["rule_coverage_outcome_counts"] = rule_coverage["coverage"][
            "outcome_counts"
        ]
    if h4_collision_report is not None:
        output["h4_collision_report"] = str(args.h4_collision_output)
        output["h4_collision_counts"] = h4_collision_report["counts_by_sub_disposition"]
    if observation_claim_report_path is not None:
        output["climate_observation_claim"] = str(observation_claim_report_path)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
