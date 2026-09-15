from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, Protocol

from src.ontology.wikimedia_world_walk import WorldBucketProjection, WorldGrowthReceipt, WorldWalkResult


MaterialisationState = Literal[
    "skeleton",
    "reference_only",
    "full_local",
    "cold_local",
    "federated_only",
]
_ALLOWED_MATERIALISATION_STATES = frozenset(
    {"skeleton", "reference_only", "full_local", "cold_local", "federated_only"}
)


class CursorLike(Protocol):
    def __enter__(self) -> "CursorLike": ...
    def __exit__(self, exc_type, exc, tb) -> object: ...
    def execute(self, sql: str, params: tuple[object, ...]) -> object: ...


class ConnectionLike(Protocol):
    def cursor(self) -> CursorLike: ...
    def commit(self) -> object: ...


@dataclass(frozen=True)
class WorldBucketPersistenceReceipt:
    bucket_id: str
    projection_id: str
    nodes_written: int
    growth_receipts_written: int
    projection_members_written: int
    candidate_only: bool = True
    semantic_promotion: bool = False


@dataclass(frozen=True)
class MaterialisationReceipt:
    receipt_id: str
    bucket_id: str
    object_id: str
    materialisation_state: MaterialisationState
    content_digest: str | None
    source_locator: str | None
    reason: str
    candidate_only: bool = True
    semantic_promotion: bool = False

    def __post_init__(self) -> None:
        if not self.receipt_id:
            raise ValueError("receipt_id must be non-empty")
        if not self.bucket_id:
            raise ValueError("bucket_id must be non-empty")
        if not self.object_id:
            raise ValueError("object_id must be non-empty")
        if self.materialisation_state not in _ALLOWED_MATERIALISATION_STATES:
            raise ValueError("unsupported materialisation_state")
        if not self.reason:
            raise ValueError("reason must be non-empty")
        if not self.candidate_only or self.semantic_promotion:
            raise ValueError("materialisation receipts are candidate-only and non-promoting")


def _feed_text(hasher: "hashlib._Hash", label: str, value: str) -> None:
    label_bytes = label.encode("utf-8")
    value_bytes = value.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(4, "little", signed=False))
    hasher.update(label_bytes)
    hasher.update(len(value_bytes).to_bytes(8, "little", signed=False))
    hasher.update(value_bytes)


def _feed_int(hasher: "hashlib._Hash", label: str, value: int) -> None:
    _feed_text(hasher, label, str(value))


def _feed_bool(hasher: "hashlib._Hash", label: str, value: bool) -> None:
    _feed_text(hasher, label, "1" if value else "0")


def _feed_growth_receipt(hasher: "hashlib._Hash", receipt: WorldGrowthReceipt) -> None:
    _feed_int(hasher, "hop", receipt.hop)
    _feed_text(hasher, "source", receipt.source)
    _feed_text(hasher, "target", receipt.target)
    _feed_text(hasher, "edge_family", receipt.edge_family)
    _feed_text(hasher, "relation", receipt.relation)
    _feed_int(hasher, "priority", receipt.priority)
    _feed_bool(hasher, "cycle", receipt.cycle)


def world_bucket_id(result: WorldWalkResult) -> str:
    """Return a deterministic identity for the complete local walk state."""

    hasher = hashlib.sha256()
    _feed_text(hasher, "schema_version", result.schema_version)
    _feed_text(hasher, "seed", result.seed)
    _feed_int(hasher, "hop_budget", result.hop_budget)
    _feed_int(hasher, "actual_hops", result.actual_hops)
    for node in result.nodes:
        _feed_text(hasher, "node", node)
    for receipt in result.receipts:
        _feed_growth_receipt(hasher, receipt)
    _feed_bool(hasher, "semantic_promotion", result.semantic_promotion)
    _feed_bool(hasher, "live_publication_performed", result.live_publication_performed)
    return "world-bucket-state:sha256:" + hasher.hexdigest()


def _sha256_bytes(value: str | None) -> bytes | None:
    if value is None:
        return None
    prefix = "sha256:"
    if not value.startswith(prefix):
        raise ValueError("only sha256 digests are accepted")
    encoded = value[len(prefix) :]
    if len(encoded) != 64 or any(character not in "0123456789abcdefABCDEF" for character in encoded):
        raise ValueError("invalid sha256 digest")
    return bytes.fromhex(encoded)


def persist_world_bucket(
    connection: ConnectionLike,
    *,
    result: WorldWalkResult,
    projection: WorldBucketProjection,
) -> WorldBucketPersistenceReceipt:
    """Persist a complete local bucket and selected projection append-only.

    The operation performs inserts only. Replaying the same deterministic
    bucket/projection is idempotent via `ON CONFLICT DO NOTHING`. The database
    migration separately rejects UPDATE and DELETE on these tables.
    """

    if projection.seed != result.seed:
        raise ValueError("projection seed must match world-walk seed")
    if projection.walk_schema_version != result.schema_version:
        raise ValueError("projection walk schema must match world-walk schema")
    if not projection.candidate_only or projection.semantic_promotion:
        raise ValueError("world-bucket projection must remain candidate-only")
    if projection.publication_projection_is_browsing_history:
        raise ValueError("publication projection must not encode browsing history")

    bucket_id = world_bucket_id(result)
    projection_id = projection.logical_shard_id
    projection_digest = _sha256_bytes(projection.content_digest)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sl_world_bucket (
                bucket_id, schema_version, walk_schema_version, seed,
                hop_budget, actual_hop_count, candidate_only, semantic_promotion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                bucket_id,
                projection.schema_version,
                result.schema_version,
                result.seed,
                result.hop_budget,
                result.actual_hops,
                True,
                False,
            ),
        )
        for ordinal, node_id in enumerate(result.nodes):
            cursor.execute(
                """
                INSERT INTO sl_world_bucket_node (bucket_id, node_id, ordinal)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (bucket_id, node_id, ordinal),
            )
        for receipt in result.receipts:
            cursor.execute(
                """
                INSERT INTO sl_world_growth_receipt (
                    bucket_id, hop, source_node_id, target_node_id,
                    edge_family, relation, priority, cycle
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    bucket_id,
                    receipt.hop,
                    receipt.source,
                    receipt.target,
                    receipt.edge_family,
                    receipt.relation,
                    receipt.priority,
                    receipt.cycle,
                ),
            )
        cursor.execute(
            """
            INSERT INTO sl_world_bucket_projection (
                projection_id, bucket_id, schema_version, compiler_version,
                logical_shard_id, packaging_target, manifest_format,
                content_addressing, content_digest, candidate_only,
                semantic_promotion, live_ipfs_publication_performed,
                publication_projection_is_browsing_history
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                projection_id,
                bucket_id,
                projection.schema_version,
                projection.compiler_version,
                projection.logical_shard_id,
                projection.packaging_target,
                projection.manifest_format,
                projection.content_addressing,
                projection_digest,
                True,
                False,
                False,
                False,
            ),
        )
        for ordinal, node_id in enumerate(projection.selected_node_ids):
            cursor.execute(
                """
                INSERT INTO sl_world_bucket_projection_member (projection_id, node_id, ordinal)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (projection_id, node_id, ordinal),
            )
    connection.commit()
    return WorldBucketPersistenceReceipt(
        bucket_id=bucket_id,
        projection_id=projection_id,
        nodes_written=len(result.nodes),
        growth_receipts_written=len(result.receipts),
        projection_members_written=len(projection.selected_node_ids),
    )


def append_materialisation_receipt(
    connection: ConnectionLike,
    receipt: MaterialisationReceipt,
) -> None:
    """Append one materialisation observation without changing semantic status."""

    digest = _sha256_bytes(receipt.content_digest)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sl_world_materialisation_receipt (
                receipt_id, bucket_id, object_id, materialisation_state,
                content_digest, source_locator, reason, candidate_only,
                semantic_promotion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                receipt.receipt_id,
                receipt.bucket_id,
                receipt.object_id,
                receipt.materialisation_state,
                digest,
                receipt.source_locator,
                receipt.reason,
                receipt.candidate_only,
                receipt.semantic_promotion,
            ),
        )
    connection.commit()
