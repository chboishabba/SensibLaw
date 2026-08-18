"""Reuse session-local numeric sentence staging relations across closures.

Sentence closure semantics remain owned by ``persist_sentence_closure_setwise``.
This strategy changes only the physical lifetime of its five temporary staging
relations: create them once per PostgreSQL session, truncate them before each
sentence, and preserve them across commits.

The old shape created and dropped five temporary tables for every sentence.
For a document with many thousands of sentence fibres that makes catalog/DDL
work scale with sentence count even though the semantic transition is already
set-wise within each fibre. Reuse removes that fixed schema churn while keeping
all sentence leases, transactions, digests, triggers and failure boundaries
unchanged.
"""

from __future__ import annotations

from typing import Any


_INSTALL_MARKER = "_reusable_numeric_sentence_staging_installed"


def _prepare_reusable_stages(cursor: Any) -> None:
    """Ensure the five session-local stages exist, then clear their prior rows."""

    # IF NOT EXISTS is deliberately retained rather than keeping Python-side
    # connection identity state. PostgreSQL session-local temp relations are the
    # authority for their own lifetime; reconnects therefore fail safe.
    cursor.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_numeric_sentence_object (
            ordinal INTEGER PRIMARY KEY,
            object_digest BYTEA NOT NULL,
            object_kind_symbol_id BIGINT NOT NULL,
            head_symbol_id BIGINT NOT NULL,
            source_token_id BIGINT NOT NULL,
            information_gain DOUBLE PRECISION NOT NULL,
            representation_cost DOUBLE PRECISION NOT NULL,
            ambiguity_cost DOUBLE PRECISION NOT NULL,
            promotion_score DOUBLE PRECISION NOT NULL,
            promoted BOOLEAN NOT NULL
        ) ON COMMIT PRESERVE ROWS;
        CREATE TEMP TABLE IF NOT EXISTS tmp_numeric_sentence_factor (
            ordinal INTEGER PRIMARY KEY,
            factor_digest BYTEA NOT NULL,
            factor_type_symbol_id BIGINT NOT NULL,
            predicate_symbol_id BIGINT NOT NULL,
            temporal_state SMALLINT NOT NULL,
            modal_state SMALLINT NOT NULL,
            support_score DOUBLE PRECISION NOT NULL
        ) ON COMMIT PRESERVE ROWS;
        CREATE TEMP TABLE IF NOT EXISTS tmp_numeric_sentence_factor_support (
            factor_ordinal INTEGER NOT NULL,
            support_ordinal INTEGER NOT NULL,
            token_id BIGINT NOT NULL,
            PRIMARY KEY (factor_ordinal, support_ordinal)
        ) ON COMMIT PRESERVE ROWS;
        CREATE TEMP TABLE IF NOT EXISTS tmp_numeric_sentence_factor_slot (
            factor_ordinal INTEGER NOT NULL,
            slot_ordinal INTEGER NOT NULL,
            role_symbol_id BIGINT NOT NULL,
            source_token_id BIGINT NOT NULL,
            resolution_state SMALLINT NOT NULL,
            required BOOLEAN NOT NULL,
            PRIMARY KEY (factor_ordinal, slot_ordinal)
        ) ON COMMIT PRESERVE ROWS;
        CREATE TEMP TABLE IF NOT EXISTS tmp_numeric_sentence_demand (
            ordinal INTEGER PRIMARY KEY,
            demand_digest BYTEA NOT NULL,
            expected_target_kind SMALLINT NOT NULL,
            expected_factor_type_symbol_id BIGINT,
            expected_object_kind_symbol_id BIGINT,
            lexical_symbol_id BIGINT,
            role_symbol_id BIGINT,
            residual_type_symbol_id BIGINT NOT NULL,
            recency_class SMALLINT NOT NULL,
            max_candidates INTEGER NOT NULL
        ) ON COMMIT PRESERVE ROWS;
        TRUNCATE TABLE
            tmp_numeric_sentence_object,
            tmp_numeric_sentence_factor,
            tmp_numeric_sentence_factor_support,
            tmp_numeric_sentence_factor_slot,
            tmp_numeric_sentence_demand
        """
    )


def install_reusable_numeric_sentence_staging() -> bool:
    """Install the physical stage-lifetime strategy exactly once."""

    from src.storage.postgres import numeric_sentence_admission as admission

    if getattr(admission, _INSTALL_MARKER, False):
        return False
    admission._create_stages = _prepare_reusable_stages
    setattr(admission, _INSTALL_MARKER, True)
    return True


__all__ = ["install_reusable_numeric_sentence_staging"]
