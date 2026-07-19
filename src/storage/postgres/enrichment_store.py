"""Relational persistence for candidate-only external PNF enrichment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Iterable

from src.ontology.external_enrichment import EnrichmentResult, canonical_sha256


def _digest(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _request_ref(provider_ref: str, lookup_key: str) -> str:
    return "external-request:" + canonical_sha256(
        {"provider_ref": provider_ref, "lookup_key": lookup_key}
    )


def persist_external_enrichment_results(
    cursor: Any,
    results: Iterable[EnrichmentResult],
    *,
    now: datetime | None = None,
    positive_ttl: timedelta = timedelta(days=30),
    negative_ttl: timedelta = timedelta(days=1),
) -> tuple[str, ...]:
    """Persist provider candidates without closing the linked resolution demand."""

    active_now = now or datetime.now(timezone.utc)
    persisted_sets: list[str] = []
    for result in results:
        demand = result.demand
        for candidate_set in result.candidate_sets:
            has_candidates = bool(candidate_set.candidates)
            expires_at = active_now + (positive_ttl if has_candidates else negative_ttl)
            request_ref = _request_ref(candidate_set.provider_ref, demand.lookup_key)
            request_identity = {
                "request_ref": request_ref,
                "lookup_key": demand.lookup_key,
                "provider_ref": candidate_set.provider_ref,
                "demand_kind": demand.demand_kind,
                "language": demand.language,
                "surface": demand.surface,
            }
            cursor.execute(
                """
                INSERT INTO enrichment.lookup_request
                    (request_ref, lookup_key_sha256, provider_ref, demand_kind_ref,
                     language_ref, query_text, request_state_ref, cache_state_ref,
                     expires_at, request_sha256)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (request_ref) DO UPDATE SET
                    request_state_ref = EXCLUDED.request_state_ref,
                    cache_state_ref = EXCLUDED.cache_state_ref,
                    expires_at = EXCLUDED.expires_at
                """,
                (
                    request_ref,
                    bytes.fromhex(demand.lookup_key),
                    candidate_set.provider_ref,
                    demand.demand_kind,
                    demand.language,
                    demand.surface,
                    "completed" if has_candidates else "completed_empty",
                    result.cache_state,
                    expires_at,
                    _digest(request_identity),
                ),
            )
            cursor.execute(
                """
                INSERT INTO enrichment.lookup_request_demand (request_ref, demand_ref)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (request_ref, demand.demand_ref),
            )
            for receipt in result.request_receipts:
                receipt_ref = str(receipt.get("request_receipt_ref") or "")
                if not receipt_ref:
                    continue
                cursor.execute(
                    """
                    INSERT INTO enrichment.provider_request_receipt
                        (request_receipt_ref, request_ref, provider_ref,
                         operation_ref, request_state_ref, response_sha256,
                         detail, receipt_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (request_receipt_ref) DO NOTHING
                    """,
                    (
                        receipt_ref,
                        request_ref,
                        str(receipt.get("provider_ref") or candidate_set.provider_ref),
                        str(receipt.get("operation") or "lookup"),
                        str(receipt.get("status") or "unknown"),
                        receipt.get("response_sha256"),
                        receipt.get("detail"),
                        _digest(receipt),
                    ),
                )
            for snapshot_ref in candidate_set.snapshot_refs:
                snapshot_identity = {
                    "snapshot_ref": snapshot_ref,
                    "provider_ref": candidate_set.provider_ref,
                }
                cursor.execute(
                    """
                    INSERT INTO enrichment.provider_snapshot
                        (snapshot_ref, provider_ref, expires_at, snapshot_sha256)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (snapshot_ref) DO NOTHING
                    """,
                    (
                        snapshot_ref,
                        candidate_set.provider_ref,
                        expires_at,
                        _digest(snapshot_identity),
                    ),
                )
            for candidate in candidate_set.candidates:
                candidate_payload = candidate.to_dict()
                cursor.execute(
                    """
                    INSERT INTO enrichment.external_candidate
                        (candidate_ref, provider_ref, external_id,
                         candidate_kind_ref, label, description, source_url,
                         provider_score, snapshot_ref, authority_state_ref,
                         candidate_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                            'candidate_only', %s)
                    ON CONFLICT (candidate_ref) DO NOTHING
                    """,
                    (
                        candidate.candidate_ref,
                        candidate.provider_ref,
                        candidate.external_id,
                        candidate.candidate_kind,
                        candidate.label,
                        candidate.description,
                        candidate.source_url,
                        candidate.provider_score,
                        candidate.snapshot_ref,
                        _digest(candidate_payload),
                    ),
                )
                for alias in candidate.aliases:
                    cursor.execute(
                        """
                        INSERT INTO enrichment.external_candidate_alias
                            (candidate_ref, language_ref, alias_text)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (candidate.candidate_ref, demand.language, alias),
                    )
                for type_ref in candidate.type_refs:
                    cursor.execute(
                        """
                        INSERT INTO enrichment.external_candidate_type
                            (candidate_ref, type_ref)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (candidate.candidate_ref, type_ref),
                    )
            set_payload = candidate_set.to_dict()
            cursor.execute(
                """
                INSERT INTO enrichment.external_candidate_set
                    (candidate_set_ref, demand_ref, subject_ref, request_ref,
                     provider_ref, member_count, authority_state_ref,
                     identity_closed, candidate_set_sha256)
                VALUES (%s, %s, %s, %s, %s, %s, 'candidate_only', FALSE, %s)
                ON CONFLICT (candidate_set_ref) DO NOTHING
                """,
                (
                    candidate_set.candidate_set_ref,
                    demand.demand_ref,
                    demand.subject_ref,
                    request_ref,
                    candidate_set.provider_ref,
                    len(candidate_set.candidates),
                    _digest(set_payload),
                ),
            )
            for ordinal, candidate in enumerate(candidate_set.candidates):
                cursor.execute(
                    """
                    INSERT INTO enrichment.external_candidate_set_member
                        (candidate_set_ref, candidate_ref, ordinal)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (candidate_set.candidate_set_ref, candidate.candidate_ref, ordinal),
                )
            for assessment in candidate_set.assessments:
                assessment_payload = assessment.to_dict()
                cursor.execute(
                    """
                    INSERT INTO enrichment.external_candidate_assessment
                        (candidate_set_ref, candidate_ref, compatibility_state_ref,
                         surface_score, type_score, context_score, combined_score,
                         reasons, assessment_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (candidate_set_ref, candidate_ref) DO NOTHING
                    """,
                    (
                        candidate_set.candidate_set_ref,
                        assessment.candidate_ref,
                        assessment.compatibility_state,
                        assessment.surface_score,
                        assessment.type_score,
                        assessment.context_score,
                        assessment.combined_score,
                        list(assessment.reasons),
                        _digest(assessment_payload),
                    ),
                )
            for residual_ref in candidate_set.residuals:
                cursor.execute(
                    """
                    INSERT INTO enrichment.external_candidate_set_residual
                        (candidate_set_ref, residual_ref)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (candidate_set.candidate_set_ref, residual_ref),
                )
            for pressure in result.pressure_receipts:
                if pressure.candidate_set_ref != candidate_set.candidate_set_ref:
                    continue
                pressure_payload = pressure.to_dict()
                cursor.execute(
                    """
                    INSERT INTO enrichment.pressure_receipt
                        (pressure_ref, demand_ref, candidate_set_ref,
                         before_total, after_total, monotone, demand_closed,
                         identity_closed, pressure_components,
                         residual_transitions, receipt_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE, FALSE,
                            %s::jsonb, %s::jsonb, %s)
                    ON CONFLICT (pressure_ref) DO NOTHING
                    """,
                    (
                        pressure.pressure_ref,
                        pressure.demand_ref,
                        pressure.candidate_set_ref,
                        pressure.before.total,
                        pressure.after.total,
                        pressure.monotone,
                        json.dumps(
                            {
                                "before": pressure.before.to_dict(),
                                "after": pressure.after.to_dict(),
                            },
                            sort_keys=True,
                        ),
                        json.dumps(
                            [dict(row) for row in pressure.residual_transitions],
                            sort_keys=True,
                        ),
                        _digest(pressure_payload),
                    ),
                )
            persisted_sets.append(candidate_set.candidate_set_ref)
    return tuple(sorted(set(persisted_sets)))


__all__ = ["persist_external_enrichment_results"]
