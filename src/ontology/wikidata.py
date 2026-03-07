from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import requests


SCHEMA_VERSION = "wikidata_projection_v0_1"
FINDER_SCHEMA_VERSION = "wikidata_qualifier_drift_finder_v0_1"
DEFAULT_FIND_QUALIFIER_PROPERTIES = ("P166", "P39", "P54", "P6")
TEMPORAL_QUALIFIER_PROPERTIES = frozenset({"P580", "P582", "P585"})
REVIEW_QUALIFIER_PROPERTIES = frozenset({"P7452"})
PARTHOOD_PROPERTIES = frozenset({"P361", "P527"})
PARTHOOD_INVERSE_RELATIONS = {
    "P361": frozenset({"P361", "P527"}),
    "P527": frozenset({"P527", "P361"}),
}
PROPERTY_PRIORITY = {
    "P166": 40,
    "P39": 35,
    "P54": 30,
    "P6": 25,
}
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
MEDIAWIKI_API_ENDPOINT = "https://www.wikidata.org/w/api.php"
ENTITY_EXPORT_TEMPLATE = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json?revision={revid}"
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SensibLaw-Wikidata-QualifierDrift/0.1",
}


@dataclass(frozen=True)
class StatementBundle:
    subject: str
    property: str
    value: Any
    rank: str
    qualifiers: tuple[tuple[str, tuple[str, ...]], ...]
    references: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]


@dataclass(frozen=True)
class WindowSlice:
    window_id: str
    bundles: tuple[StatementBundle, ...]


def _stringify(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _extract_datavalue(raw: Any) -> Any:
    if not isinstance(raw, Mapping):
        return raw
    value = raw.get("value")
    if isinstance(value, Mapping):
        if "id" in value:
            return value["id"]
        if "text" in value:
            return value["text"]
        if "time" in value:
            return value["time"]
        if "amount" in value:
            return value["amount"]
    return value


def _normalize_value_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, (list, tuple)):
        return tuple(sorted(_stringify(item) for item in value))
    return (_stringify(value),)


def _normalize_qualifiers(raw: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if raw is None:
        return tuple()
    if isinstance(raw, Mapping):
        items = raw.items()
    elif isinstance(raw, list):
        pairs: list[tuple[str, Any]] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("qualifier list entries must be objects")
            prop = item.get("property")
            if prop is None:
                raise ValueError("qualifier list entries require property")
            pairs.append((_stringify(prop), item.get("value")))
        items = pairs
    else:
        raise ValueError("qualifiers must be an object or list")
    return tuple(
        sorted((_stringify(prop), _normalize_value_list(value)) for prop, value in items)
    )


def _normalize_references(raw: Any) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    if raw is None:
        return tuple()
    if not isinstance(raw, list):
        raise ValueError("references must be a list")
    blocks: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
    for block in raw:
        if not isinstance(block, Mapping):
            raise ValueError("reference blocks must be objects")
        normalized = tuple(
            sorted((_stringify(prop), _normalize_value_list(value)) for prop, value in block.items())
        )
        blocks.append(normalized)
    return tuple(sorted(blocks))


def _parse_bundle(raw: Mapping[str, Any]) -> StatementBundle:
    subject = raw.get("subject")
    prop = raw.get("property")
    if not subject or not prop:
        raise ValueError("statement bundles require subject and property")
    return StatementBundle(
        subject=_stringify(subject),
        property=_stringify(prop),
        value=raw.get("value"),
        rank=_stringify(raw.get("rank", "normal")),
        qualifiers=_normalize_qualifiers(raw.get("qualifiers")),
        references=_normalize_references(raw.get("references")),
    )


def _extract_references_from_wikidata(raw_refs: Any) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    if not isinstance(raw_refs, list):
        return tuple()
    blocks: list[dict[str, list[Any]]] = []
    for ref in raw_refs:
        if not isinstance(ref, Mapping):
            continue
        snaks = ref.get("snaks")
        if not isinstance(snaks, Mapping):
            continue
        block: dict[str, list[Any]] = {}
        for prop, snak_list in snaks.items():
            if not isinstance(snak_list, list):
                continue
            values: list[Any] = []
            for snak in snak_list:
                if not isinstance(snak, Mapping):
                    continue
                datavalue = snak.get("datavalue")
                extracted = _extract_datavalue(datavalue)
                if extracted is not None:
                    values.append(extracted)
            if values:
                block[_stringify(prop)] = values
        if block:
            blocks.append(block)
    return _normalize_references(blocks)


def _extract_qualifiers_from_wikidata(raw_quals: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not isinstance(raw_quals, Mapping):
        return tuple()
    normalized: dict[str, list[Any]] = {}
    for prop, snak_list in raw_quals.items():
        if not isinstance(snak_list, list):
            continue
        values: list[Any] = []
        for snak in snak_list:
            if not isinstance(snak, Mapping):
                continue
            extracted = _extract_datavalue(snak.get("datavalue"))
            if extracted is not None:
                values.append(extracted)
        if values:
            normalized[_stringify(prop)] = values
    return _normalize_qualifiers(normalized)


def load_windows(payload: Mapping[str, Any]) -> tuple[WindowSlice, ...]:
    raw_windows = payload.get("windows")
    if not isinstance(raw_windows, list) or not raw_windows:
        raise ValueError("payload requires non-empty windows list")
    windows: list[WindowSlice] = []
    for index, raw_window in enumerate(raw_windows):
        if not isinstance(raw_window, Mapping):
            raise ValueError("window entries must be objects")
        window_id = raw_window.get("id") or f"window_{index + 1}"
        raw_bundles = raw_window.get("statement_bundles")
        if not isinstance(raw_bundles, list):
            raise ValueError("window entries require statement_bundles list")
        windows.append(
            WindowSlice(
                window_id=_stringify(window_id),
                bundles=tuple(_parse_bundle(bundle) for bundle in raw_bundles),
            )
        )
    return tuple(windows)


def build_slice_from_entity_exports(
    window_sources: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    property_filter: Iterable[str] | None = None,
) -> Dict[str, Any]:
    allowed = tuple(sorted(set(property_filter or ("P31", "P279"))))
    windows: list[dict[str, Any]] = []
    for window_id, sources in window_sources.items():
        bundles: list[dict[str, Any]] = []
        source_labels: list[str] = []
        for source in sources:
            source_name = _stringify(source.get("_source_path", "unknown"))
            source_labels.append(source_name)
            entities = source.get("entities")
            if not isinstance(entities, Mapping):
                raise ValueError("entity export payload requires top-level entities object")
            for entity_id, entity in sorted(entities.items()):
                if not isinstance(entity, Mapping):
                    continue
                claims = entity.get("claims")
                if not isinstance(claims, Mapping):
                    continue
                for prop in allowed:
                    claim_list = claims.get(prop)
                    if not isinstance(claim_list, list):
                        continue
                    for statement in claim_list:
                        if not isinstance(statement, Mapping):
                            continue
                        mainsnak = statement.get("mainsnak")
                        if not isinstance(mainsnak, Mapping):
                            continue
                        extracted = _extract_datavalue(mainsnak.get("datavalue"))
                        if extracted is None:
                            continue
                        bundles.append(
                            {
                                "subject": _stringify(entity_id),
                                "property": prop,
                                "value": extracted,
                                "rank": _stringify(statement.get("rank", "normal")),
                                "qualifiers": dict(_extract_qualifiers_from_wikidata(statement.get("qualifiers"))),
                                "references": [
                                    {key: list(values) for key, values in block}
                                    for block in _extract_references_from_wikidata(statement.get("references"))
                                ],
                            }
                        )
        windows.append(
            {
                "id": _stringify(window_id),
                "statement_bundles": bundles,
                "source_files": sorted(source_labels),
            }
        )
    return {
        "metadata": {
            "generated_by": "build_slice_from_entity_exports",
            "properties": list(allowed),
        },
        "windows": windows,
    }


def _extract_qid(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def _sparql_candidate_query(property_pid: str, *, row_limit: int) -> str:
    return f"""
SELECT ?item ?statement ?qualifier_pid
WHERE {{
  ?item p:{property_pid} ?statement .
  ?statement ?pq ?qv .
  FILTER(STRSTARTS(STR(?pq), "http://www.wikidata.org/prop/qualifier/"))
  BIND(STRAFTER(STR(?pq), "http://www.wikidata.org/prop/qualifier/") AS ?qualifier_pid)
}}
LIMIT {max(1, int(row_limit))}
""".strip()


def _http_get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    timeout_seconds: int = 30,
) -> Any:
    response = requests.get(
        url,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=max(1, int(timeout_seconds)),
    )
    response.raise_for_status()
    return response.json()


def _collect_current_qualifier_candidates(
    *,
    property_filter: Sequence[str],
    candidate_limit: int,
    timeout_seconds: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for property_pid in property_filter:
        query = _sparql_candidate_query(
            property_pid,
            row_limit=max(candidate_limit * 3, 30),
        )
        try:
            payload = _http_get_json(
                SPARQL_ENDPOINT,
                params={"format": "json", "query": query},
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            failures.append(
                {
                    "stage": "candidate_query",
                    "property_pid": property_pid,
                    "error": _stringify(exc),
                }
            )
            continue
        bindings = payload.get("results", {}).get("bindings", [])
        statement_groups: dict[tuple[str, str], set[str]] = {}
        for row in bindings:
            item_raw = row.get("item", {}).get("value")
            statement_uri = row.get("statement", {}).get("value")
            qualifier_pid = row.get("qualifier_pid", {}).get("value")
            if not item_raw or not statement_uri or not qualifier_pid:
                continue
            qid = _extract_qid(item_raw)
            statement_id = _extract_qid(statement_uri)
            candidate = grouped.setdefault(
                (qid, property_pid),
                {
                    "qid": qid,
                    "label": qid,
                    "property_pid": property_pid,
                    "statement_ids": set(),
                    "qualifier_properties": set(),
                    "statement_qualifier_sets": [],
                },
            )
            candidate["statement_ids"].add(statement_id)
            candidate["qualifier_properties"].add(qualifier_pid)
            statement_groups.setdefault((qid, statement_id), set()).add(qualifier_pid)
        for (qid, statement_id), qualifier_set in statement_groups.items():
            candidate = grouped[(qid, property_pid)]
            candidate["statement_qualifier_sets"].append(tuple(sorted(qualifier_set)))

    results: list[dict[str, Any]] = []
    for (qid, property_pid), candidate in sorted(grouped.items()):
        qualifier_properties = sorted(candidate["qualifier_properties"])
        results.append(
            {
                "qid": qid,
                "label": candidate["label"],
                "property_pid": property_pid,
                "statement_count": len(candidate["statement_ids"]),
                "qualifier_property_count": len(qualifier_properties),
                "qualifier_properties": qualifier_properties,
                "statement_qualifier_sets": sorted(
                    {
                        item
                        for item in candidate["statement_qualifier_sets"]
                    },
                    key=lambda item: (len(item), item),
                ),
            }
        )
    return results, failures


def _fetch_recent_revisions(
    qid: str,
    *,
    revision_limit: int,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    payload = _http_get_json(
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
    if not isinstance(pages, Mapping) or not pages:
        return []
    page = next(iter(pages.values()))
    revisions = page.get("revisions", [])
    if not isinstance(revisions, list):
        return []
    return [
        {"revid": int(item["revid"]), "timestamp": _stringify(item["timestamp"])}
        for item in revisions
        if isinstance(item, Mapping) and "revid" in item and "timestamp" in item
    ]


def _fetch_entity_export_revision(qid: str, revid: int, *, timeout_seconds: int) -> dict[str, Any]:
    url = ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=revid)
    payload = _http_get_json(url, timeout_seconds=timeout_seconds)
    if not isinstance(payload, dict):
        raise ValueError(f"entity export must be an object for {qid}@{revid}")
    return payload


def _slot_reports_from_entity_export(
    payload: Mapping[str, Any],
    *,
    property_filter: Sequence[str],
    e0: int = 1,
) -> dict[str, dict[str, Any]]:
    slice_payload = build_slice_from_entity_exports(
        {"scan": [dict(payload)]},
        property_filter=property_filter,
    )
    windows = load_windows(slice_payload)
    return _aggregate_window(windows[0], e0=e0)


def _compare_slot_reports_for_qualifier_drift(
    left_slots: Mapping[str, Mapping[str, Any]],
    right_slots: Mapping[str, Mapping[str, Any]],
    *,
    from_window: str,
    to_window: str,
) -> list[dict[str, Any]]:
    all_slot_ids = sorted(set(left_slots) | set(right_slots))
    findings: list[dict[str, Any]] = []
    for slot_id in all_slot_ids:
        left = left_slots.get(
            slot_id,
            {
                "qualifier_signatures": [],
                "qualifier_property_set": [],
                "qualifier_entropy": 0.0,
            },
        )
        right = right_slots.get(
            slot_id,
            {
                "qualifier_signatures": [],
                "qualifier_property_set": [],
                "qualifier_entropy": 0.0,
            },
        )
        signatures_changed = left["qualifier_signatures"] != right["qualifier_signatures"]
        property_set_changed = left["qualifier_property_set"] != right["qualifier_property_set"]
        entropy_delta = round(right["qualifier_entropy"] - left["qualifier_entropy"], 6)
        if not signatures_changed and not property_set_changed and entropy_delta == 0.0:
            continue
        severity = "low"
        if property_set_changed:
            severity = "high"
        elif signatures_changed:
            severity = "medium"
        findings.append(
            {
                "slot_id": slot_id,
                "subject_qid": slot_id.split("|", 1)[0],
                "property_pid": slot_id.split("|", 1)[1],
                "from_window": from_window,
                "to_window": to_window,
                "qualifier_signatures_t1": left["qualifier_signatures"],
                "qualifier_signatures_t2": right["qualifier_signatures"],
                "qualifier_property_set_t1": left["qualifier_property_set"],
                "qualifier_property_set_t2": right["qualifier_property_set"],
                "qualifier_entropy_t1": left["qualifier_entropy"],
                "qualifier_entropy_t2": right["qualifier_entropy"],
                "qualifier_entropy_delta": entropy_delta,
                "severity": severity,
            }
        )
    findings.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}[item["severity"]],
            item["slot_id"],
        )
    )
    return findings


def _score_candidate(candidate: Mapping[str, Any], revisions: Sequence[Mapping[str, Any]]) -> tuple[int, list[str]]:
    property_pid = _stringify(candidate["property_pid"])
    qualifier_properties = set(candidate.get("qualifier_properties", []))
    statement_count = int(candidate.get("statement_count", 0))
    score = PROPERTY_PRIORITY.get(property_pid, 10)
    reasons = [f"property_priority:{PROPERTY_PRIORITY.get(property_pid, 10)}"]
    if len(qualifier_properties) >= 2:
        score += 15
        reasons.append("multi_qualifier_property_bonus:15")
    qualifier_property_points = len(qualifier_properties) * 5
    if qualifier_property_points:
        score += qualifier_property_points
        reasons.append(f"qualifier_property_count_bonus:{qualifier_property_points}")
    if qualifier_properties & TEMPORAL_QUALIFIER_PROPERTIES:
        score += 8
        reasons.append("temporal_qualifier_bonus:8")
    if qualifier_properties & REVIEW_QUALIFIER_PROPERTIES:
        score += 8
        reasons.append("review_qualifier_bonus:8")
    if statement_count > 1:
        statement_bonus = min((statement_count - 1) * 3, 12)
        score += statement_bonus
        reasons.append(f"multi_statement_bonus:{statement_bonus}")
    revision_bonus = min(max(len(revisions) - 1, 0), 10)
    if revision_bonus:
        score += revision_bonus
        reasons.append(f"revision_pair_bonus:{revision_bonus}")
    return score, reasons


def find_qualifier_drift_candidates(
    *,
    property_filter: Iterable[str] | None = None,
    candidate_limit: int = 20,
    revision_limit: int = 5,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    allowed = tuple(sorted(set(property_filter or DEFAULT_FIND_QUALIFIER_PROPERTIES)))
    raw_candidates, failures = _collect_current_qualifier_candidates(
        property_filter=allowed,
        candidate_limit=candidate_limit,
        timeout_seconds=timeout_seconds,
    )
    if not raw_candidates and failures:
        return {
            "schema_version": FINDER_SCHEMA_VERSION,
            "candidate_query_mode": "per_property_raw_rows_v1",
            "properties": list(allowed),
            "candidate_limit": int(candidate_limit),
            "revision_limit": int(revision_limit),
            "timeout_seconds": int(timeout_seconds),
            "candidate_count": 0,
            "scanned_candidate_count": 0,
            "candidates": [],
            "confirmed_drift_cases": [],
            "stable_baselines": [],
            "failures": failures,
        }
    entity_cache: dict[tuple[str, int], dict[str, Any]] = {}
    ranked_candidates: list[dict[str, Any]] = []
    confirmed_drift_cases: list[dict[str, Any]] = []
    stable_baselines: list[dict[str, Any]] = []

    for candidate in raw_candidates:
        qid = candidate["qid"]
        property_pid = candidate["property_pid"]
        try:
            revisions = _fetch_recent_revisions(
                qid,
                revision_limit=revision_limit,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            failures.append(
                {
                    "qid": qid,
                    "label": candidate["label"],
                    "property_pid": property_pid,
                    "stage": "revision_metadata",
                    "error": _stringify(exc),
                }
            )
            continue

        score, ranking_reasons = _score_candidate(candidate, revisions)
        ranked_candidates.append(
            {
                **candidate,
                "score": score,
                "ranking_reasons": ranking_reasons,
                "recent_revisions": revisions,
                "recent_revision_ids": [item["revid"] for item in revisions],
            }
        )

    ranked_candidates.sort(
        key=lambda item: (-item["score"], item["qid"], item["property_pid"])
    )

    for candidate in ranked_candidates[: max(1, int(candidate_limit))]:
        qid = candidate["qid"]
        property_pid = candidate["property_pid"]
        revisions = candidate["recent_revision_ids"]
        revision_meta = {
            item["revid"]: item["timestamp"]
            for item in candidate["recent_revisions"]
        }
        if len(revisions) < 2:
            stable_baselines.append(
                {
                    "qid": qid,
                    "label": candidate["label"],
                    "property_pid": property_pid,
                    "score": candidate["score"],
                    "recent_revision_ids": revisions,
                    "scanned_pairs": 0,
                    "status": "insufficient_revisions",
                }
            )
            continue

        found_case = None
        had_failure = False
        scanned_pairs = 0
        for index in range(len(revisions) - 1):
            newer_revid = revisions[index]
            older_revid = revisions[index + 1]
            scanned_pairs += 1
            try:
                older_payload = entity_cache.setdefault(
                    (qid, older_revid),
                    _fetch_entity_export_revision(
                        qid,
                        older_revid,
                        timeout_seconds=timeout_seconds,
                    ),
                )
                newer_payload = entity_cache.setdefault(
                    (qid, newer_revid),
                    _fetch_entity_export_revision(
                        qid,
                        newer_revid,
                        timeout_seconds=timeout_seconds,
                    ),
                )
                older_slots = _slot_reports_from_entity_export(
                    older_payload,
                    property_filter=(property_pid,),
                )
                newer_slots = _slot_reports_from_entity_export(
                    newer_payload,
                    property_filter=(property_pid,),
                )
                drift = _compare_slot_reports_for_qualifier_drift(
                    older_slots,
                    newer_slots,
                    from_window=str(older_revid),
                    to_window=str(newer_revid),
                )
            except Exception as exc:
                failures.append(
                    {
                        "qid": qid,
                        "label": candidate["label"],
                        "property_pid": property_pid,
                        "stage": "revision_compare",
                        "from_revision": older_revid,
                        "to_revision": newer_revid,
                        "error": _stringify(exc),
                    }
                )
                had_failure = True
                break
            if drift:
                found_case = {
                    "qid": qid,
                    "label": candidate["label"],
                    "property_pid": property_pid,
                    "score": candidate["score"],
                    "ranking_reasons": candidate["ranking_reasons"],
                    "statement_count": candidate["statement_count"],
                    "qualifier_properties": candidate["qualifier_properties"],
                    "from_revision": {
                        "revid": older_revid,
                        "timestamp": revision_meta.get(older_revid, "unknown"),
                    },
                    "to_revision": {
                        "revid": newer_revid,
                        "timestamp": revision_meta.get(newer_revid, "unknown"),
                    },
                    "qualifier_drift": drift,
                    "entity_export_urls": {
                        "from": ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=older_revid),
                        "to": ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=newer_revid),
                    },
                    "suggested_fixture_stem": f"{qid.lower()}_{property_pid.lower()}_{older_revid}_{newer_revid}",
                }
                break
        if found_case:
            confirmed_drift_cases.append(found_case)
            continue
        if had_failure:
            continue
        stable_baselines.append(
            {
                "qid": qid,
                "label": candidate["label"],
                "property_pid": property_pid,
                "score": candidate["score"],
                "recent_revision_ids": revisions,
                "scanned_pairs": scanned_pairs,
                "status": "stable",
            }
        )

    return {
        "schema_version": FINDER_SCHEMA_VERSION,
        "candidate_query_mode": "per_property_raw_rows_v1",
        "properties": list(allowed),
        "candidate_limit": int(candidate_limit),
        "revision_limit": int(revision_limit),
        "timeout_seconds": int(timeout_seconds),
        "candidate_count": len(ranked_candidates),
        "scanned_candidate_count": len(confirmed_drift_cases) + len(stable_baselines),
        "candidates": ranked_candidates[: max(1, int(candidate_limit))],
        "confirmed_drift_cases": confirmed_drift_cases,
        "stable_baselines": stable_baselines,
        "failures": failures,
    }


def _qualifier_signature(qualifiers: tuple[tuple[str, tuple[str, ...]], ...]) -> str:
    return json.dumps(qualifiers, ensure_ascii=False, separators=(",", ":"))


def _reference_metrics(
    references: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]
) -> tuple[int, int, int]:
    n_blocks = len(references)
    distinct_sources = set()
    has_time = 0
    for block in references:
        for prop, values in block:
            if prop == "P248":
                distinct_sources.update(values)
            if prop in {"P577", "P813", "retrieved", "publication_date"} and values:
                has_time = 1
    return n_blocks, len(distinct_sources), has_time


def _project_bundle(bundle: StatementBundle, *, e0: int) -> Dict[str, Any]:
    n_refs, n_sources, has_time = _reference_metrics(bundle.references)
    evidence = min(n_refs + n_sources + has_time, 9)
    tau = 0
    if evidence >= e0:
        if bundle.rank == "preferred":
            tau = 1
        elif bundle.rank == "deprecated":
            tau = -1
    return {
        "tau": tau,
        "evidence": evidence,
        "conflict": 0,
        "audit": {
            "rule_ids": ["base", "quals", "refs", "rank"],
            "rank": bundle.rank,
            "qualifier_signature": _qualifier_signature(bundle.qualifiers),
            "reference_block_count": n_refs,
            "distinct_sources": n_sources,
            "has_time_reference": bool(has_time),
        },
    }


def _aggregate_window(window: WindowSlice, *, e0: int) -> Dict[str, Any]:
    slots: dict[tuple[str, str], dict[str, Any]] = {}
    for bundle in window.bundles:
        slot_key = (bundle.subject, bundle.property)
        projected = _project_bundle(bundle, e0=e0)
        slot = slots.setdefault(
            slot_key,
            {
                "subject_qid": bundle.subject,
                "property_pid": bundle.property,
                "bundle_count": 0,
                "taus": [],
                "sum_e": 0,
                "sum_c": 0,
                "audit": [],
                "qualifier_signatures": [],
                "qualifier_property_sets": [],
            },
        )
        qualifier_props = tuple(prop for prop, _ in bundle.qualifiers)
        slot["bundle_count"] += 1
        slot["taus"].append(projected["tau"])
        slot["sum_e"] += projected["evidence"]
        slot["sum_c"] += projected["conflict"]
        slot["audit"].append(projected["audit"])
        slot["qualifier_signatures"].append(projected["audit"]["qualifier_signature"])
        slot["qualifier_property_sets"].append(qualifier_props)

    result_slots: dict[str, dict[str, Any]] = {}
    for subject, prop in sorted(slots):
        slot = slots[(subject, prop)]
        signature_counts: dict[str, int] = {}
        for signature in slot["qualifier_signatures"]:
            signature_counts[signature] = signature_counts.get(signature, 0) + 1
        total_signatures = len(slot["qualifier_signatures"]) or 1
        qualifier_entropy = 0.0
        for count in signature_counts.values():
            probability = count / total_signatures
            qualifier_entropy -= probability * math.log2(probability)
        qualifier_property_set = sorted(
            {
                prop_name
                for prop_tuple in slot["qualifier_property_sets"]
                for prop_name in prop_tuple
            }
        )
        taus = set(slot["taus"])
        if taus == {1}:
            tau_star = 1
        elif taus == {-1}:
            tau_star = -1
        elif 1 in taus and -1 in taus:
            tau_star = 0
            slot["sum_c"] += 1
        else:
            tau_star = 0
        result_slots[f"{subject}|{prop}"] = {
            "subject_qid": subject,
            "property_pid": prop,
            "tau": tau_star,
            "sum_e": slot["sum_e"],
            "sum_c": slot["sum_c"],
            "bundle_count": slot["bundle_count"],
            "audit": slot["audit"],
            "qualifier_signatures": sorted(signature_counts),
            "qualifier_property_set": qualifier_property_set,
            "qualifier_entropy": round(qualifier_entropy, 6),
        }
    return result_slots


def _build_edges(window: WindowSlice, prop: str) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for bundle in window.bundles:
        if bundle.property != prop:
            continue
        target = _stringify(bundle.value)
        edges.append((bundle.subject, target))
    return sorted(edges)


def _tarjan_scc(edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    adjacency: dict[str, list[str]] = {}
    nodes = set()
    for source, target in edges:
        nodes.add(source)
        nodes.add(target)
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, [])
    for neighbors in adjacency.values():
        neighbors.sort()

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in adjacency.get(node, []):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while stack:
                current = stack.pop()
                on_stack.remove(current)
                component.append(current)
                if current == node:
                    break
            components.append(sorted(component))

    for node in sorted(nodes):
        if node not in indices:
            strongconnect(node)
    return sorted((component for component in components if len(component) > 1), key=lambda c: (len(c), c))


def _find_mixed_order_nodes(window: WindowSlice) -> list[dict[str, Any]]:
    roles: dict[str, set[str]] = {}
    evidence: dict[str, list[dict[str, str]]] = {}
    for bundle in window.bundles:
        if bundle.property == "P31":
            roles.setdefault(bundle.subject, set()).add("subject_p31")
            value = _stringify(bundle.value)
            roles.setdefault(value, set()).add("value_p31")
            evidence.setdefault(bundle.subject, []).append(
                {"property_pid": "P31", "role": "subject", "value_qid": value}
            )
            evidence.setdefault(value, []).append(
                {"property_pid": "P31", "role": "value", "subject_qid": bundle.subject}
            )
        elif bundle.property == "P279":
            target = _stringify(bundle.value)
            roles.setdefault(bundle.subject, set()).add("subject_p279")
            roles.setdefault(target, set()).add("value_p279")
            evidence.setdefault(bundle.subject, []).append(
                {"property_pid": "P279", "role": "subject", "value_qid": target}
            )
            evidence.setdefault(target, []).append(
                {"property_pid": "P279", "role": "value", "subject_qid": bundle.subject}
            )

    findings: list[dict[str, Any]] = []
    for node in sorted(roles):
        node_roles = roles[node]
        if "subject_p31" in node_roles and ("subject_p279" in node_roles or "value_p279" in node_roles):
            findings.append(
                {
                    "qid": node,
                    "roles": sorted(node_roles),
                    "audit_trace": sorted(
                        evidence.get(node, []),
                        key=lambda item: (
                            item["property_pid"],
                            item["role"],
                            item.get("subject_qid", ""),
                            item.get("value_qid", ""),
                        ),
                    ),
                }
            )
    return findings


def _find_metaclass_candidates(window: WindowSlice) -> list[dict[str, Any]]:
    incoming_p31: dict[str, int] = {}
    higher_order_targets: set[str] = set()
    for bundle in window.bundles:
        if bundle.property == "P31":
            target = _stringify(bundle.value)
            incoming_p31[target] = incoming_p31.get(target, 0) + 1
        if bundle.property in {"P31", "P279"}:
            higher_order_targets.add(bundle.subject)

    findings: list[dict[str, Any]] = []
    for target in sorted(incoming_p31):
        if target not in higher_order_targets:
            continue
        incoming = incoming_p31[target]
        findings.append(
            {
                "qid": target,
                "p31_incoming_count": incoming,
                "metaclass_ratio": 1.0,
            }
        )
    return findings


def _infer_node_type(
    node: str, instances: set[str], classes: set[str]
) -> str:
    if node in instances and node in classes:
        return "ambiguous"
    if node in instances:
        return "instance"
    if node in classes:
        return "class"
    return "unknown"


def _build_parthood_typing(window: WindowSlice) -> dict[str, Any]:
    instances: set[str] = set()
    classes: set[str] = set()
    for bundle in window.bundles:
        if bundle.property != "P31":
            continue
        instances.add(bundle.subject)
        classes.add(_stringify(bundle.value))

    parthood_edges: set[tuple[str, str, str]] = set()
    for bundle in window.bundles:
        if bundle.property not in PARTHOOD_PROPERTIES:
            continue
        subject = bundle.subject
        value = _stringify(bundle.value)
        parthood_edges.add((bundle.property, subject, value))

    typing_rows: list[dict[str, Any]] = []
    redundant_pairs: set[tuple[str, str, str]] = set()
    counts: dict[str, int] = {
        "class->class": 0,
        "instance->class": 0,
        "instance->instance": 0,
        "ambiguous": 0,
        "abstained": 0,
        "mixed_redundant": 0,
        "cross_property_inverse": 0,
    }
    for property_pid, subject, value in sorted(parthood_edges):
        subject_type = _infer_node_type(subject, instances, classes)
        value_type = _infer_node_type(value, instances, classes)
        bucket = "abstained"
        confidence = "abstain"
        reasons: list[str] = []
        inverse_properties: list[str] = []
        for inverse_property in sorted(PARTHOOD_INVERSE_RELATIONS.get(property_pid, frozenset())):
            if (inverse_property, value, subject) in parthood_edges:
                inverse_properties.append(inverse_property)
        inverse_present = bool(inverse_properties)
        inverse_relation = (
            "same_property_redundant" if property_pid in inverse_properties else "cross_property_expected" if inverse_present else "none"
        )

        if subject_type == "class" and value_type == "class":
            bucket = "class->class"
        elif subject_type == "instance" and value_type == "class":
            bucket = "instance->class"
        elif subject_type == "instance" and value_type == "instance":
            bucket = "instance->instance"
        elif subject_type == "ambiguous" or value_type == "ambiguous":
            bucket = "ambiguous"
            reasons.append("ambiguous_node_type")
        elif subject_type == "unknown" or value_type == "unknown":
            bucket = "abstained"
            reasons.append("insufficient_classification_evidence")
        else:
            bucket = "mixed"
            reasons.append("mixed_type_profile")

        if bucket in {"class->class", "instance->class", "instance->instance"}:
            confidence = "certain"
            counts[bucket] += 1
        elif bucket == "ambiguous":
            counts["ambiguous"] += 1
        else:
            counts["abstained"] += 1

        if inverse_relation == "cross_property_expected":
            counts["cross_property_inverse"] += 1

        if inverse_relation == "same_property_redundant" and bucket in {"class->class", "instance->instance"}:
            pair_key = (property_pid, *sorted((subject, value)))
            if pair_key not in redundant_pairs:
                counts["mixed_redundant"] += 1
                redundant_pairs.add(pair_key)

        typing_rows.append(
            {
                "slot_id": f"{subject}|{property_pid}|{value}",
                "subject_qid": subject,
                "value_qid": value,
                "property_pid": property_pid,
                "bucket": bucket,
                "subject_type": subject_type,
                "value_type": value_type,
                "classification": confidence,
                "inverse_properties": inverse_properties,
                "inverse_relation": inverse_relation,
                "reasons": sorted(set(reasons)),
                "inverse_present": inverse_present,
                "mixed_redundancy_flag": inverse_relation == "same_property_redundant" and bucket == "instance->instance",
            }
        )

    return {
        "classifications": sorted(
            typing_rows,
            key=lambda item: (item["property_pid"], item["subject_qid"], item["value_qid"]),
        ),
        "counts": counts,
    }


def _build_qualifier_drift(
    slot_reports: Mapping[str, Mapping[str, Mapping[str, Any]]],
    windows: Sequence[WindowSlice],
) -> list[dict[str, Any]]:
    if len(windows) < 2:
        return []
    first = windows[0].window_id
    second = windows[1].window_id
    return _compare_slot_reports_for_qualifier_drift(
        slot_reports[first],
        slot_reports[second],
        from_window=first,
        to_window=second,
    )


def project_wikidata_payload(
    payload: Mapping[str, Any], *, e0: int = 1, property_filter: Iterable[str] | None = None
) -> Dict[str, Any]:
    windows = load_windows(payload)
    allowed = tuple(sorted(set(property_filter or ("P31", "P279"))))
    filtered_windows = tuple(
        WindowSlice(
            window_id=window.window_id,
            bundles=tuple(bundle for bundle in window.bundles if bundle.property in allowed),
        )
        for window in windows
    )

    window_reports: list[dict[str, Any]] = []
    slot_reports: dict[str, dict[str, Any]] = {}
    for window in filtered_windows:
        slots = _aggregate_window(window, e0=e0)
        slot_reports[window.window_id] = slots
        p279_edges = _build_edges(window, "P279")
        sccs = _tarjan_scc(p279_edges)
        mixed_order_nodes = _find_mixed_order_nodes(window)
        metaclass_candidates = _find_metaclass_candidates(window)
        window_reports.append(
            {
                "id": window.window_id,
                "bundle_count": len(window.bundles),
                "slot_count": len(slots),
                "slots": [slots[key] | {"slot_id": key} for key in sorted(slots)],
                "diagnostics": {
                    "p279_sccs": [
                        {"scc_id": f"{window.window_id}:scc:{idx + 1}", "members": members, "size": len(members)}
                        for idx, members in enumerate(sccs)
                    ],
                    "mixed_order_nodes": mixed_order_nodes,
                    "metaclass_candidates": metaclass_candidates,
                    "parthood_typing": _build_parthood_typing(window),
                },
            }
        )

    unstable_slots: list[dict[str, Any]] = []
    if len(filtered_windows) >= 2:
        first = filtered_windows[0].window_id
        second = filtered_windows[1].window_id
        all_slot_ids = sorted(set(slot_reports[first]) | set(slot_reports[second]))
        for slot_id in all_slot_ids:
            left_present = slot_id in slot_reports[first]
            right_present = slot_id in slot_reports[second]
            left = slot_reports[first].get(slot_id, {"tau": 0, "sum_e": 0, "sum_c": 0})
            right = slot_reports[second].get(slot_id, {"tau": 0, "sum_e": 0, "sum_c": 0})
            delta_e = right["sum_e"] - left["sum_e"]
            delta_c = right["sum_c"] - left["sum_c"]
            indicator = 1 if left["tau"] != right["tau"] else 0
            if indicator or delta_e or delta_c:
                severity = "low"
                if indicator and left["tau"] != 0 and right["tau"] != 0:
                    severity = "high"
                elif indicator:
                    severity = "medium"
                unstable_slots.append(
                    {
                        "slot_id": slot_id,
                        "subject_qid": slot_id.split("|", 1)[0],
                        "property_pid": slot_id.split("|", 1)[1],
                        "from_window": first,
                        "to_window": second,
                        "tau_t1": left["tau"],
                        "tau_t2": right["tau"],
                        "delta_e": delta_e,
                        "delta_c": delta_c,
                        "eii": indicator,
                        "present_in_both": left_present and right_present,
                        "severity": severity,
                    }
                )
        unstable_slots.sort(
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}[item["severity"]],
                -item["eii"],
                -(1 if item["present_in_both"] else 0),
                item["slot_id"],
            )
        )

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in unstable_slots:
        severity_counts[item["severity"]] += 1
    qualifier_drift = _build_qualifier_drift(slot_reports, filtered_windows)
    qualifier_severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in qualifier_drift:
        qualifier_severity_counts[item["severity"]] += 1

    review_summary = {
        "next_bounded_slice_recommendation": "Qualifier drift is now active; expand qualifier-bearing slices and review property-set instability before wider ontology phases.",
        "unstable_slot_counts": severity_counts,
        "top_unstable_slot_ids": [item["slot_id"] for item in unstable_slots[:5]],
        "structural_focus": [
            "mixed_order_nodes",
            "p279_sccs",
            "metaclass_candidates",
            "parthood_typing",
        ],
        "qualifier_drift_counts": qualifier_severity_counts,
        "top_qualifier_drift_slot_ids": [item["slot_id"] for item in qualifier_drift[:5]],
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "bounded_slice": {"properties": list(allowed), "window_ids": [window.window_id for window in filtered_windows]},
        "assumptions": {
            "rank_evidence_gate_e0": e0,
            "advisory_only": True,
            "tokenizer_lexeme_boundary_preserved": True,
        },
        "windows": window_reports,
        "unstable_slots": unstable_slots,
        "qualifier_drift": qualifier_drift,
        "review_summary": review_summary,
    }


__all__ = [
    "SCHEMA_VERSION",
    "FINDER_SCHEMA_VERSION",
    "build_slice_from_entity_exports",
    "find_qualifier_drift_candidates",
    "load_windows",
    "project_wikidata_payload",
]
