"""Durable source admission, legal-source selection, and parity receipts."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

from src.pnf.legal_adjunct import LegalSourcePlan, NormativeInteractionDemand
from src.pnf.legal_source_registry import RegisteredLegalSource
from src.policy.carriers.canonical import canonical_sha256
from src.sources.admission import SourceAdmissionReceipt


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def persist_source_admission_receipts(
    cursor: Any,
    *,
    corpus_ref: str,
    receipts: Iterable[SourceAdmissionReceipt | Mapping[str, Any]],
) -> tuple[str, ...]:
    rows: list[tuple[Any, ...]] = []
    refs: list[str] = []
    for value in receipts:
        payload = value.to_dict() if isinstance(value, SourceAdmissionReceipt) else dict(value)
        refs.append(str(payload["receipt_ref"]))
        rows.append(
            (
                payload["receipt_ref"],
                corpus_ref,
                payload["source_revision_ref"],
                payload["source_role"],
                payload["semantic_scope"],
                payload["admission_state"],
                payload.get("exclusion_reason"),
                payload["profile_ref"],
                payload.get("contract_ref") or "source-admission:v0_2",
                _sha(payload),
            )
        )
    if rows:
        cursor.executemany(
            """
            INSERT INTO source_admission_receipt
                (receipt_ref, corpus_ref, source_revision_ref, source_role,
                 semantic_scope, admission_state, exclusion_reason, profile_ref,
                 contract_ref, receipt_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (receipt_ref) DO NOTHING
            """,
            rows,
        )
    return tuple(sorted(set(refs)))


def persist_legal_source_revision(
    cursor: Any,
    source: RegisteredLegalSource | Mapping[str, Any],
) -> str:
    payload = source.to_dict() if isinstance(source, RegisteredLegalSource) else dict(source)
    cursor.execute(
        """
        INSERT INTO legal_source_revision
            (source_revision_ref, document_ref, admission_receipt_ref,
             acquisition_receipt_ref, jurisdiction_ref, source_role,
             authority_level, temporal_refs, provider_profile_refs, media_type,
             canonical_text_sha256, compile_eligible, revision_sha256)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
             %s, %s, TRUE, %s)
        ON CONFLICT (source_revision_ref) DO NOTHING
        """,
        (
            payload["source_revision_ref"],
            payload["document_ref"],
            payload["admission_receipt_ref"],
            payload.get("acquisition_receipt_ref"),
            payload["jurisdiction_ref"],
            payload["source_role"],
            payload["authority_level"],
            _json(payload.get("temporal_refs") or ()),
            _json(payload.get("provider_profile_refs") or ()),
            payload.get("media_type") or "text/plain",
            payload["canonical_text_sha256"],
            _sha(payload),
        ),
    )
    return str(payload["source_revision_ref"])


def load_compatible_legal_sources(
    cursor: Any,
    demand: NormativeInteractionDemand,
) -> tuple[RegisteredLegalSource, ...]:
    """Load only persisted revisions compatible with an explicit legal demand."""

    if not demand.acquisition_ready:
        return ()
    cursor.execute(
        """
        SELECT source_revision_ref, document_ref, admission_receipt_ref,
               acquisition_receipt_ref, jurisdiction_ref, source_role,
               authority_level, temporal_refs, provider_profile_refs, media_type,
               canonical_text_sha256, compile_eligible
        FROM legal_source_revision
        WHERE compile_eligible = TRUE
          AND jurisdiction_ref = ANY(%s)
          AND source_role = ANY(%s)
          AND authority_level = ANY(%s)
        ORDER BY source_revision_ref
        """,
        (
            list(demand.jurisdiction_refs),
            list(demand.source_role_refs),
            list(demand.authority_level_refs),
        ),
    )
    rows: list[RegisteredLegalSource] = []
    for row in cursor.fetchall():
        temporal_refs = tuple(str(value) for value in (row[7] or ()))
        provider_refs = tuple(str(value) for value in (row[8] or ()))
        if (
            demand.temporal_refs
            and temporal_refs
            and not set(demand.temporal_refs).intersection(temporal_refs)
        ):
            continue
        if (
            demand.provider_profile_refs
            and not set(demand.provider_profile_refs).intersection(provider_refs)
        ):
            continue
        rows.append(
            RegisteredLegalSource(
                source_revision_ref=str(row[0]),
                document_ref=str(row[1]),
                admission_receipt_ref=str(row[2]),
                acquisition_receipt_ref=str(row[3]) if row[3] else None,
                jurisdiction_ref=str(row[4]),
                source_role=str(row[5]),
                authority_level=str(row[6]),
                temporal_refs=temporal_refs,
                provider_profile_refs=provider_refs,
                media_type=str(row[9]),
                canonical_text_sha256=str(row[10]),
                compile_eligible=bool(row[11]),
            )
        )
    return tuple(rows)


def load_legal_source_payload(
    cursor: Any,
    *,
    source_revision_ref: str,
) -> Mapping[str, Any] | None:
    cursor.execute(
        """
        SELECT l.source_revision_ref, l.document_ref, l.media_type,
               l.canonical_text_sha256, convert_from(c.payload, 'UTF8')
        FROM legal_source_revision AS l
        JOIN corpus.document AS d ON d.document_ref = l.document_ref
        JOIN corpus.canonical_content AS c ON c.canonical_ref = d.canonical_ref
        WHERE l.source_revision_ref = %s AND l.compile_eligible = TRUE
        """,
        (source_revision_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "source_revision_ref": str(row[0]),
        "document_ref": str(row[1]),
        "media_type": str(row[2]),
        "canonical_text_sha256": str(row[3]),
        "canonical_text": str(row[4]),
    }


def persist_legal_source_plans(
    cursor: Any,
    plans: Sequence[LegalSourcePlan],
) -> tuple[str, ...]:
    rows = []
    refs = []
    for plan in plans:
        payload = plan.to_dict()
        plan_ref = "legal-source-plan:" + canonical_sha256(payload)
        refs.append(plan_ref)
        rows.append(
            (
                plan_ref,
                plan.demand_ref,
                plan.plan_key,
                plan.state,
                _json(plan.selected_source_revision_refs),
                _json(plan.blocked_reasons),
                _sha(payload),
            )
        )
    if rows:
        cursor.executemany(
            """
            INSERT INTO legal_source_plan_receipt
                (plan_ref, demand_ref, plan_key, state,
                 selected_source_revision_refs, blocked_reasons, plan_sha256)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (plan_ref) DO NOTHING
            """,
            rows,
        )
    return tuple(sorted(refs))


def persist_governed_acquisition_receipt(
    cursor: Any,
    receipt: Mapping[str, Any],
) -> str:
    cursor.execute(
        """
        INSERT INTO governed_acquisition_receipt
            (receipt_ref, request_ref, operator_authorization_ref,
             provider_profile_ref, requested_url, final_url,
             source_revision_ref, content_sha256, media_type, byte_count,
             state, failure_reason, receipt_sha256)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (receipt_ref) DO NOTHING
        """,
        (
            receipt["receipt_ref"],
            receipt["request_ref"],
            receipt["operator_authorization_ref"],
            receipt["provider_profile_ref"],
            receipt["requested_url"],
            receipt.get("final_url"),
            receipt.get("source_revision_ref"),
            receipt.get("content_sha256"),
            receipt.get("media_type"),
            int(receipt.get("byte_count") or 0),
            receipt["state"],
            receipt.get("failure_reason"),
            _sha(receipt),
        ),
    )
    return str(receipt["receipt_ref"])


def persist_transaction_attempt(
    cursor: Any,
    *,
    document_ref: str,
    build_key_sha256: str,
    attempt_no: int,
    state: str,
    sqlstate: str | None,
    retry_delay_ms: int,
    worker_ref: str,
) -> str:
    payload = {
        "document_ref": document_ref,
        "build_key_sha256": build_key_sha256,
        "attempt_no": attempt_no,
        "state": state,
        "sqlstate": sqlstate,
        "retry_delay_ms": retry_delay_ms,
        "worker_ref": worker_ref,
    }
    attempt_ref = "document-transaction-attempt:" + canonical_sha256(payload)
    cursor.execute(
        """
        INSERT INTO execution_document_transaction_attempt
            (attempt_ref, document_ref, build_key_sha256, attempt_no, state,
             sqlstate, retry_delay_ms, worker_ref, telemetry_sha256)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (attempt_ref) DO NOTHING
        """,
        (
            attempt_ref,
            document_ref,
            build_key_sha256,
            attempt_no,
            state,
            sqlstate,
            retry_delay_ms,
            worker_ref,
            _sha(payload),
        ),
    )
    return attempt_ref


def persist_parity_receipt(cursor: Any, receipt: Mapping[str, Any]) -> str:
    cursor.execute(
        """
        INSERT INTO curated_legal_ir_parity_receipt
            (receipt_ref, corpus_ref, admission_profile_ref,
             compiler_contract_ref, source_revision_refs, ordinary_graph_refs,
             legal_graph_refs, demand_refs, plan_refs, legal_ir_refs,
             typed_meet_refs, legacy_witness_refs, identity_snapshot,
             control_snapshot, identity_parity, network_attempt_count,
             unexpected_failure_refs, receipt_sha256)
        VALUES
            (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
             %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
             %s::jsonb, %s, %s, %s::jsonb, %s)
        ON CONFLICT (receipt_ref) DO NOTHING
        """,
        (
            receipt["receipt_ref"],
            receipt["corpus_ref"],
            receipt["admission_profile_ref"],
            receipt["compiler_contract_ref"],
            _json(receipt.get("source_revision_refs") or ()),
            _json(receipt.get("ordinary_graph_refs") or ()),
            _json(receipt.get("legal_graph_refs") or ()),
            _json(receipt.get("demand_refs") or ()),
            _json(receipt.get("plan_refs") or ()),
            _json(receipt.get("legal_ir_refs") or ()),
            _json(receipt.get("typed_meet_refs") or ()),
            _json(receipt.get("legacy_witness_refs") or ()),
            _json(receipt["identity_snapshot"]),
            (
                _json(receipt["control_snapshot"])
                if receipt.get("control_snapshot") is not None
                else None
            ),
            receipt.get("identity_parity"),
            int(receipt.get("network_attempt_count") or 0),
            _json(receipt.get("unexpected_failure_refs") or ()),
            _sha(receipt),
        ),
    )
    return str(receipt["receipt_ref"])


__all__ = [
    "load_compatible_legal_sources",
    "load_legal_source_payload",
    "persist_governed_acquisition_receipt",
    "persist_legal_source_plans",
    "persist_legal_source_revision",
    "persist_parity_receipt",
    "persist_source_admission_receipts",
    "persist_transaction_attempt",
]
