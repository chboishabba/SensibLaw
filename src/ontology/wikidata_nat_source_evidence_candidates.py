from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


SOURCE_EVIDENCE_CANDIDATE_PLAN_SCHEMA_VERSION = (
    "sl.nat_source_evidence_candidate_plan.v0_1"
)
SOURCE_EVIDENCE_CANDIDATE_SCHEMA_VERSION = "sl.nat_source_evidence_candidate.v0_1"

_SCOPE_CUES = {
    "Q124883250": ("scope 1", "scope1"),
    "Q124883301": ("scope 2", "scope2"),
    "Q124883330": ("scope 2", "scope2", "market-based", "market based"),
    "Q124883327": ("scope 2", "scope2", "location-based", "location based"),
    "Q124883309": ("scope 3", "scope3"),
}


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
        raise ValueError("invalid canonical-text relative path")
    root_path = Path(root).resolve()
    path = (root_path / relative).resolve()
    try:
        path.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("canonical-text path escapes configured store root") from exc
    return path


def _load_verified_canonical(
    materialization: Mapping[str, Any], *, materialized_store_dir: str | Path
) -> dict[str, Any]:
    expected = _text(materialization.get("canonical_text_digest"))
    if not expected.startswith("sha256:"):
        raise ValueError("materialization lacks canonical sha256 digest")
    path = _safe_store_path(
        materialized_store_dir,
        _text(materialization.get("canonical_text_relpath")),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("canonical text artifact must be a JSON object")
    observed = "sha256:" + canonical_sha256(payload)
    if observed != expected:
        raise ValueError("canonical text artifact no longer matches materialization receipt")
    return payload


def _years_from_claim(claim: Mapping[str, Any]) -> list[str]:
    qualifiers = _mapping(claim.get("qualifiers"))
    years: set[str] = set()
    for prop in ("P585", "P580", "P582"):
        for raw in _sequence(qualifiers.get(prop)):
            match = re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", _text(raw))
            if match:
                years.add(match.group(0))
    return sorted(years)


def _scope_qids(claim: Mapping[str, Any]) -> list[str]:
    qualifiers = _mapping(claim.get("qualifiers"))
    return sorted({_text(value) for value in _sequence(qualifiers.get("P3831")) if _text(value)})


def _quantity_variants(raw_value: str) -> list[str]:
    value = raw_value.strip()
    if not value:
        return []
    unsigned = value.lstrip("+")
    variants = {value, unsigned}
    match = re.fullmatch(r"(-?)(\d+)(?:\.(\d+))?", unsigned)
    if match:
        sign, integer, fraction = match.groups()
        grouped_comma = f"{int(integer):,}" if integer else integer
        grouped_space = grouped_comma.replace(",", " ")
        grouped_nbsp = grouped_comma.replace(",", "\u00a0")
        grouped_nnbsp = grouped_comma.replace(",", "\u202f")
        for grouped in (grouped_comma, grouped_space, grouped_nbsp, grouped_nnbsp):
            rendered = sign + grouped
            if fraction is not None:
                variants.add(rendered + "." + fraction)
                variants.add(rendered + "," + fraction)
            else:
                variants.add(rendered)
    return sorted((variant for variant in variants if variant), key=lambda item: (-len(item), item))


def _quantity_matches(text: str, variants: Sequence[str]) -> list[tuple[int, int, str]]:
    matches: dict[tuple[int, int], str] = {}
    for variant in variants:
        escaped = re.escape(variant)
        # Source reports often use ordinary, NBSP or narrow-NBSP thousands grouping.
        escaped = escaped.replace(r"\ ", r"[ \u00a0\u202f]")
        pattern = re.compile(rf"(?<![\d.,]){escaped}(?![\d.,])")
        for match in pattern.finditer(text):
            matches.setdefault((match.start(), match.end()), match.group(0))
    return [(start, end, matches[(start, end)]) for start, end in sorted(matches)]


def _overlap_page(canonical: Mapping[str, Any], start: int, end: int) -> int | None:
    for segment in _sequence(canonical.get("segments")):
        if not isinstance(segment, Mapping):
            continue
        segment_start = int(segment.get("start_char", -1) or -1)
        segment_end = int(segment.get("end_char", -1) or -1)
        if segment_end <= start or segment_start >= end:
            continue
        anchors = _mapping(segment.get("anchors"))
        page = anchors.get("page")
        if isinstance(page, int):
            return page
    return None


def _candidate_for_match(
    *,
    demand: Mapping[str, Any],
    materialization: Mapping[str, Any],
    canonical: Mapping[str, Any],
    start: int,
    end: int,
    matched_quantity: str,
    window_chars: int,
) -> dict[str, Any]:
    proposition = _mapping(demand.get("proposition"))
    claim = _mapping(proposition.get("source_claim_bundle"))
    full_text = _text(canonical.get("text"))
    window_start = max(0, start - window_chars)
    window_end = min(len(full_text), end + window_chars)
    excerpt = full_text[window_start:window_end]
    excerpt_fold = excerpt.casefold()
    expected_years = _years_from_claim(claim)
    observed_years = [year for year in expected_years if year in excerpt]
    scope_qids = _scope_qids(claim)
    observed_scope_cues: list[str] = []
    for qid in scope_qids:
        for cue in _SCOPE_CUES.get(qid, ()):
            if cue.casefold() in excerpt_fold:
                observed_scope_cues.append(cue)
    observed_scope_cues = sorted(set(observed_scope_cues))

    matched_axes = ["quantity"]
    if observed_years:
        matched_axes.append("year")
    if observed_scope_cues:
        matched_axes.append("scope_cue")
    score = len(matched_axes)
    page = _overlap_page(canonical, start, end)
    payload_without_ref = {
        "schema_version": SOURCE_EVIDENCE_CANDIDATE_SCHEMA_VERSION,
        "source_verification_demand_ref": _text(demand.get("demand_ref")),
        "source_residual_ref": _text(demand.get("source_residual_ref")),
        "source_row_ref": _text(demand.get("source_row_ref")),
        "statement_reference": _text(demand.get("statement_reference")),
        "source_fetch_receipt_ref": _text(
            materialization.get("source_fetch_receipt_ref")
        ),
        "source_content_digest": _text(materialization.get("source_content_digest")),
        "canonical_text_digest": _text(materialization.get("canonical_text_digest")),
        "locator": {
            "page": page,
            "start_char": window_start,
            "end_char": window_end,
            "quantity_start_char": start,
            "quantity_end_char": end,
        },
        "excerpt": excerpt,
        "matched_quantity": matched_quantity,
        "expected_years": expected_years,
        "observed_years": observed_years,
        "scope_qids": scope_qids,
        "observed_scope_cues": observed_scope_cues,
        "matched_axes": matched_axes,
        "candidate_score": score,
        "candidate_only": True,
        "proposition_support_evaluated": False,
        "source_support_paid": False,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["candidate_ref"] = "nat-source-evidence-candidate:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def build_source_evidence_candidate_plan(
    verification_plan: Mapping[str, Any],
    media_dispatch: Mapping[str, Any],
    *,
    materialized_store_dir: str | Path,
    max_candidates_per_demand: int = 8,
    window_chars: int = 500,
) -> dict[str, Any]:
    """Narrow exact proposition demands to page/character evidence candidates.

    Candidate compilation is intentionally weaker than verification. Quantity/year/
    scope-cue co-occurrence can prioritize passages for adjudication, but cannot emit
    ``supported`` or ``contradicted`` and cannot pay source support.
    """

    materializations = {
        _text(item.get("source_fetch_receipt_ref")): item
        for item in _sequence(media_dispatch.get("materializations"))
        if isinstance(item, Mapping)
        and _text(item.get("source_fetch_receipt_ref"))
        and item.get("state") == "materialized"
    }
    results: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []

    demands = [
        demand
        for demand in _sequence(verification_plan.get("demands"))
        if isinstance(demand, Mapping)
    ]
    demands.sort(key=lambda item: _text(item.get("demand_ref")))
    for demand in demands:
        demand_ref = _text(demand.get("demand_ref"))
        if demand.get("state") != "ready":
            results.append(
                {
                    "source_verification_demand_ref": demand_ref,
                    "state": "blocked_upstream_verification_demand",
                    "candidate_count": 0,
                    "candidate_refs": [],
                    "proposition_support_evaluated": False,
                    "source_support_paid": False,
                }
            )
            continue

        proposition = _mapping(demand.get("proposition"))
        claim = _mapping(proposition.get("source_claim_bundle"))
        variants = _quantity_variants(_text(claim.get("value")))
        demand_candidates: list[dict[str, Any]] = []
        found_materialized_source = False
        for artifact in _sequence(demand.get("source_artifacts")):
            if not isinstance(artifact, Mapping):
                continue
            receipt_ref = _text(artifact.get("receipt_ref"))
            materialization = materializations.get(receipt_ref)
            if materialization is None:
                continue
            found_materialized_source = True
            canonical = _load_verified_canonical(
                materialization,
                materialized_store_dir=materialized_store_dir,
            )
            text = _text(canonical.get("text"))
            for start, end, matched_quantity in _quantity_matches(text, variants):
                demand_candidates.append(
                    _candidate_for_match(
                        demand=demand,
                        materialization=materialization,
                        canonical=canonical,
                        start=start,
                        end=end,
                        matched_quantity=matched_quantity,
                        window_chars=window_chars,
                    )
                )

        demand_candidates.sort(
            key=lambda item: (
                -int(item.get("candidate_score", 0) or 0),
                item.get("locator", {}).get("page") or 10**9,
                item.get("locator", {}).get("quantity_start_char") or 0,
                _text(item.get("candidate_ref")),
            )
        )
        demand_candidates = demand_candidates[: max(1, int(max_candidates_per_demand))]
        all_candidates.extend(demand_candidates)
        if demand_candidates:
            state = "candidate_spans_found"
        elif found_materialized_source:
            state = "open_no_quantity_anchor_found"
        else:
            state = "blocked_media_not_materialized"
        results.append(
            {
                "source_verification_demand_ref": demand_ref,
                "state": state,
                "candidate_count": len(demand_candidates),
                "candidate_refs": [
                    _text(item.get("candidate_ref")) for item in demand_candidates
                ],
                "proposition_support_evaluated": False,
                "source_support_paid": False,
            }
        )

    results.sort(key=lambda item: _text(item.get("source_verification_demand_ref")))
    all_candidates.sort(key=lambda item: _text(item.get("candidate_ref")))
    payload_without_ref = {
        "schema_version": SOURCE_EVIDENCE_CANDIDATE_PLAN_SCHEMA_VERSION,
        "source_verification_plan_ref": _text(verification_plan.get("plan_ref")),
        "source_media_dispatch_ref": _text(media_dispatch.get("dispatch_ref")),
        "demand_count": len(results),
        "candidate_count": len(all_candidates),
        "demands_with_candidates_count": sum(
            1 for item in results if item.get("state") == "candidate_spans_found"
        ),
        "open_no_quantity_anchor_count": sum(
            1 for item in results if item.get("state") == "open_no_quantity_anchor_found"
        ),
        "blocked_count": sum(
            1
            for item in results
            if _text(item.get("state")).startswith("blocked_")
        ),
        "demand_results": results,
        "candidates": all_candidates,
        "candidate_generation_policy": {
            "quantity_anchor_required": True,
            "year_and_scope_are_ranking_cues_only": True,
            "string_cooccurrence_pays_source_support": False,
            "max_candidates_per_demand": max(1, int(max_candidates_per_demand)),
            "window_chars": max(1, int(window_chars)),
        },
        "proposition_support_evaluated": False,
        "source_support_paid_count": 0,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["plan_ref"] = "nat-source-evidence-candidate-plan:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = [
    "SOURCE_EVIDENCE_CANDIDATE_PLAN_SCHEMA_VERSION",
    "SOURCE_EVIDENCE_CANDIDATE_SCHEMA_VERSION",
    "build_source_evidence_candidate_plan",
]
