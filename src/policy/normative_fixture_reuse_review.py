"""Bounded normative excerpt-pack fixture quality and profile-reuse review.

This module is intentionally narrow. It reviews already-supplied fixture
payloads and, only when their bounded/provenance contract passes, replays them
through the existing canonical text adapter and normative_policy projector.

It performs no discovery, catalogue fetch, PAS crawl, or other external I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.ingestion.media_adapter import TextDocumentMediaAdapter
from src.policy.normative_policy_profile import build_normative_policy_extract

SCHEMA_VERSION = "sl.normative_fixture_reuse_review.v0_1"
REVIEW_SCOPE = "bounded_excerpt_pack_fixture_quality_and_profile_reuse"
PARSE_PROFILE = "normative_policy"
MAX_EXCERPT_CHARS = 4096


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _fixture_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []

    text = payload.get("text")
    if not _nonempty_string(text):
        issues.append("excerpt_missing_or_empty")
    elif len(text) > MAX_EXCERPT_CHARS:
        issues.append("excerpt_too_large")

    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        issues.append("provenance_missing")
        return issues

    if not _nonempty_string(provenance.get("document_ref")):
        issues.append("document_ref_missing")
    if provenance.get("source_class") != "text_source":
        issues.append("source_class_not_text_source")
    if provenance.get("source_subtype") != "excerpt_pack":
        issues.append("source_subtype_not_excerpt_pack")

    clause_refs = provenance.get("clause_refs")
    if (
        not isinstance(clause_refs, list)
        or not clause_refs
        or not all(_nonempty_string(ref) for ref in clause_refs)
    ):
        issues.append("clause_refs_missing")

    return issues


def review_normative_excerpt_packs(
    fixtures: Iterable[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Review bounded excerpt fixtures and prove shared-profile reuse by replay.

    Invalid fixtures are held before parser/profile execution. Valid fixtures
    are adapted and projected through the same production normative_policy
    path already used by the bounded ISO fixtures.
    """

    rows: list[dict[str, Any]] = []
    document_refs: set[str] = set()
    clause_refs: set[str] = set()

    for fixture_name, payload in fixtures:
        issues = _fixture_issues(payload)
        provenance = payload.get("provenance")
        provenance_dict = provenance if isinstance(provenance, dict) else {}

        document_ref = provenance_dict.get("document_ref")
        if _nonempty_string(document_ref):
            document_refs.add(document_ref.strip())

        raw_clause_refs = provenance_dict.get("clause_refs")
        if isinstance(raw_clause_refs, list):
            clause_refs.update(
                ref.strip() for ref in raw_clause_refs if _nonempty_string(ref)
            )

        bounded = not any(
            issue in {"excerpt_missing_or_empty", "excerpt_too_large"}
            for issue in issues
        )
        provenance_complete = not any(
            issue
            in {
                "provenance_missing",
                "document_ref_missing",
                "source_class_not_text_source",
                "source_subtype_not_excerpt_pack",
                "clause_refs_missing",
            }
            for issue in issues
        )

        profile_reused = False
        statement_count = 0
        query_count = 0

        if not issues:
            adapter = TextDocumentMediaAdapter(
                source_artifact_ref=f"fixture:{fixture_name}"
            )
            canonical = adapter.adapt(payload)
            extract = build_normative_policy_extract(
                canonical,
                ingest_receipt={
                    "source_artifact_ref": f"fixture:{fixture_name}",
                },
            )
            profile_reused = extract.get("parse_profile") == PARSE_PROFILE
            statement_count = len(extract.get("policy_statements", []))
            query_count = len(extract.get("ir_queries", []))
            if not profile_reused:
                issues.append("normative_policy_profile_not_reused")

        rows.append(
            {
                "fixture_name": fixture_name,
                "bounded": bounded,
                "provenance_complete": provenance_complete,
                "profile_reused": profile_reused,
                "statement_count": statement_count,
                "query_count": query_count,
                "quality_status": (
                    "fixture_quality_pass"
                    if not issues and profile_reused
                    else "fixture_quality_hold"
                ),
                "issues": issues,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "review_scope": REVIEW_SCOPE,
        "broad_catalog_ingestion_used": False,
        "parse_profile": PARSE_PROFILE,
        "pack_count": len(rows),
        "all_packs_bounded": all(row["bounded"] for row in rows),
        "all_packs_provenance_complete": all(
            row["provenance_complete"] for row in rows
        ),
        "all_packs_reuse_profile": all(row["profile_reused"] for row in rows),
        "document_refs": sorted(document_refs),
        "clause_refs": sorted(clause_refs),
        "packs": rows,
    }
