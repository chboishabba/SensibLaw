"""PostgreSQL-backed immutable semantic stage cache."""

from __future__ import annotations

import json
from typing import Any

from src.pnf.stage_cache import StageCacheEntry, StageReuseReceipt


def _json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


class PostgresStageCache:
    def __init__(self, store: Any):
        self.store = store

    def load(self, stage_build_key: str) -> StageCacheEntry | None:
        with self.store.transaction() as cursor:
            cursor.execute(
                """
                SELECT document_ref, stage, contract_ref, input_refs,
                       declaration_refs, output_ref, output_payload
                FROM semantic_stage_build_cache
                WHERE stage_build_key = %s
                """,
                (stage_build_key,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return StageCacheEntry(
            stage_build_key=stage_build_key,
            document_ref=str(row[0]),
            stage=str(row[1]),
            contract_ref=str(row[2]),
            input_refs=tuple(row[3] or ()),
            declaration_refs=tuple(row[4] or ()),
            output_ref=str(row[5]),
            output_payload=dict(row[6] or {}),
        )

    def persist(self, entry: StageCacheEntry) -> None:
        with self.store.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO semantic_stage_build_cache
                    (stage_build_key, document_ref, stage, contract_ref,
                     input_refs, declaration_refs, output_ref, output_payload)
                VALUES
                    (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb)
                ON CONFLICT (stage_build_key) DO NOTHING
                """,
                (
                    entry.stage_build_key,
                    entry.document_ref,
                    entry.stage,
                    entry.contract_ref,
                    _json(entry.input_refs),
                    _json(entry.declaration_refs),
                    entry.output_ref,
                    _json(entry.output_payload),
                ),
            )
            cursor.execute(
                """
                SELECT document_ref, stage, contract_ref, input_refs,
                       declaration_refs, output_ref, output_payload
                FROM semantic_stage_build_cache
                WHERE stage_build_key = %s
                """,
                (entry.stage_build_key,),
            )
            persisted = cursor.fetchone()
        if persisted is None:
            raise RuntimeError("stage cache insert did not persist")
        persisted_entry = StageCacheEntry(
            stage_build_key=entry.stage_build_key,
            document_ref=str(persisted[0]),
            stage=str(persisted[1]),
            contract_ref=str(persisted[2]),
            input_refs=tuple(persisted[3] or ()),
            declaration_refs=tuple(persisted[4] or ()),
            output_ref=str(persisted[5]),
            output_payload=dict(persisted[6] or {}),
        )
        if persisted_entry.to_dict() != entry.to_dict():
            raise ValueError("stage build key collision with different payload")


def persist_stage_reuse_receipt(cursor: Any, receipt: StageReuseReceipt) -> None:
    cursor.execute(
        """
        INSERT INTO semantic_stage_reuse_receipt
            (receipt_ref, document_ref, stage, stage_build_key, reused,
             source_output_ref, semantic_state_promoted)
        VALUES (%s, %s, %s, %s, %s, %s, FALSE)
        ON CONFLICT (receipt_ref) DO NOTHING
        """,
        (
            receipt.receipt_ref,
            receipt.document_ref,
            receipt.stage,
            receipt.stage_build_key,
            receipt.reused,
            receipt.source_output_ref,
        ),
    )


__all__ = ["PostgresStageCache", "persist_stage_reuse_receipt"]
