from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence


SUBJECT_FAMILY_INDEX_SCHEMA_VERSION = "sl.wikidata_subject_family_index.v0_1"
COMPANY_TYPE_QIDS = frozenset({"Q4830453", "Q6881511", "Q891723"})


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    items = [_stringify(item) for item in value]
    return sorted({item for item in items if item})


def _extract_closure_qids(evidence: Any) -> list[str]:
    if isinstance(evidence, Mapping):
        for key in (
            "type_closure",
            "closure_qids",
            "closure",
            "types",
            "ancestor_qids",
            "subject_type_closure",
        ):
            values = _string_list(evidence.get(key))
            if values:
                return values
            nested = evidence.get(key)
            if isinstance(nested, Mapping):
                for nested_key in ("qids", "items", "values"):
                    nested_values = _string_list(nested.get(nested_key))
                    if nested_values:
                        return nested_values
    return _string_list(evidence)


def _extract_source_revision_ids(evidence: Any) -> list[str]:
    if not isinstance(evidence, Mapping):
        return []
    for key in ("source_revision_ids", "revision_ids", "revisions", "source_revisions"):
        values = _string_list(evidence.get(key))
        if values:
            return values
    return []


def resolve_subject_family(closure_qids: Sequence[str]) -> str:
    closure_set = {str(qid).strip() for qid in closure_qids if str(qid).strip()}
    if closure_set & COMPANY_TYPE_QIDS:
        return "company"
    if closure_set:
        return "non_company"
    return "unknown"


def _closure_signature(closure_qids: Sequence[str]) -> str:
    digest = hashlib.sha256("\n".join(closure_qids).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def build_subject_family_index(
    subject_closure_by_qid: Mapping[str, Any],
    *,
    cache: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(subject_closure_by_qid, Mapping):
        raise ValueError("subject_closure_by_qid must be a mapping")

    cache_lookup = cache if isinstance(cache, Mapping) else {}
    subject_rows: list[dict[str, Any]] = []
    cache_index: dict[str, dict[str, Any]] = {}
    family_counts: dict[str, int] = {"company": 0, "non_company": 0, "unknown": 0}
    cache_hit_count = 0

    for subject_qid in sorted(str(key) for key in subject_closure_by_qid.keys()):
        evidence = subject_closure_by_qid.get(subject_qid)
        closure_qids = _string_list(_extract_closure_qids(evidence))
        source_revision_ids = _string_list(_extract_source_revision_ids(evidence))
        family = resolve_subject_family(closure_qids)
        closure_signature = _closure_signature(closure_qids)
        cache_key = f"{subject_qid}:{closure_signature}"
        cached_entry = cache_lookup.get(cache_key)
        cache_hit = isinstance(cached_entry, Mapping) and _stringify(cached_entry.get("closure_signature")) == closure_signature

        row = {
            "subject_qid": subject_qid,
            "family": family,
            "closure_qids": closure_qids,
            "closure_signature": closure_signature,
            "cache_key": cache_key,
            "cache_hit": cache_hit,
            "evidence_source_count": len(source_revision_ids),
            "source_revision_ids": source_revision_ids,
        }
        subject_rows.append(row)
        cache_index[cache_key] = {
            "subject_qid": subject_qid,
            "family": family,
            "closure_qids": closure_qids,
            "closure_signature": closure_signature,
            "source_revision_ids": source_revision_ids,
        }
        family_counts[family] = family_counts.get(family, 0) + 1
        if cache_hit:
            cache_hit_count += 1

    subject_count = len(subject_rows)
    return {
        "schema_version": SUBJECT_FAMILY_INDEX_SCHEMA_VERSION,
        "summary": {
            "subject_count": subject_count,
            "family_counts": family_counts,
            "cache_hit_count": cache_hit_count,
            "cache_miss_count": subject_count - cache_hit_count,
            "cache_ready": subject_count > 0,
        },
        "subject_families": subject_rows,
        "cache_index": cache_index,
    }


__all__ = [
    "COMPANY_TYPE_QIDS",
    "SUBJECT_FAMILY_INDEX_SCHEMA_VERSION",
    "build_subject_family_index",
    "resolve_subject_family",
]
