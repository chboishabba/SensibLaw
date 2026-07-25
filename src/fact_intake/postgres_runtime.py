"""Canonical PostgreSQL runtime for fact review and follow projections.

SQLite is not a runtime fallback.  Historical SQLite fixtures may be imported by
``legacy_sqlite_import`` before invoking this module, after which all reads and
writes use PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence

from src.policy.follow_projection import FollowProjection
from src.storage.postgres.follow_projection_store import (
    FollowProjectionQueryResult,
    persist_follow_projection,
    query_follow_projection,
)

POSTGRES_FACT_REVIEW_RUNTIME_CONTRACT = "sl.fact_review.postgres_single_spine.v0_1"


@dataclass(frozen=True)
class PostgresFactReviewReceipt:
    projection_ref: str
    build_seconds: float
    persistence_seconds: float
    query_seconds: float
    node_count: int
    edge_count: int
    runtime_contract: str = POSTGRES_FACT_REVIEW_RUNTIME_CONTRACT

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_ref": self.projection_ref,
            "build_seconds": self.build_seconds,
            "persistence_seconds": self.persistence_seconds,
            "query_seconds": self.query_seconds,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "runtime_contract": self.runtime_contract,
            "postgresql_semantic_authority": True,
            "sqlite_runtime_authority": False,
            "json_semantic_input": False,
        }


@dataclass(frozen=True)
class PostgresFactReviewResult:
    query_result: FollowProjectionQueryResult
    receipt: PostgresFactReviewReceipt

    def project_review_surface(self) -> dict[str, Any]:
        payload = self.query_result.presentation_payload()
        payload["runtime_receipt"] = self.receipt.to_dict()
        payload["presentation_only"] = True
        return payload


def run_postgres_fact_review(
    *,
    connection: Any,
    build_projection: Callable[[], FollowProjection],
) -> PostgresFactReviewResult:
    build_started = perf_counter()
    projection = build_projection()
    build_seconds = perf_counter() - build_started

    persist_started = perf_counter()
    with connection.cursor() as cursor:
        projection_ref = persist_follow_projection(cursor, projection)
    connection.commit()
    persistence_seconds = perf_counter() - persist_started

    query_started = perf_counter()
    with connection.cursor() as cursor:
        result = query_follow_projection(cursor, projection_ref)
    query_seconds = perf_counter() - query_started

    return PostgresFactReviewResult(
        query_result=result,
        receipt=PostgresFactReviewReceipt(
            projection_ref=projection_ref,
            build_seconds=build_seconds,
            persistence_seconds=persistence_seconds,
            query_seconds=query_seconds,
            node_count=len(projection.nodes),
            edge_count=len(projection.edges),
        ),
    )


def require_postgres_runtime_configuration(configuration: Mapping[str, Any]) -> str:
    database_url = str(configuration.get("database_url") or "").strip()
    sqlite_path = str(configuration.get("sqlite_path") or configuration.get("db_path") or "").strip()
    if sqlite_path:
        raise ValueError(
            "SQLite is deprecated as a semantic runtime; use the explicit legacy import command"
        )
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("fact-review runtime requires a PostgreSQL database_url")
    return database_url


__all__ = [
    "POSTGRES_FACT_REVIEW_RUNTIME_CONTRACT",
    "PostgresFactReviewReceipt",
    "PostgresFactReviewResult",
    "require_postgres_runtime_configuration",
    "run_postgres_fact_review",
]
