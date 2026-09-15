from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence


WORLD_BUCKET_SCHEMA_VERSION = "sl.wikimedia_world_bucket.v0_1"
WORLD_WALK_SCHEMA_VERSION = "sl.wikimedia_world_walk.v0_1"


@dataclass(frozen=True)
class EdgeCandidate:
    source: str
    target: str
    edge_family: str
    relation: str
    priority: int = 0


@dataclass(frozen=True)
class WorldWalkPolicy:
    hop_budget: int = 100
    selections_per_hop: int = 1

    def __post_init__(self) -> None:
        if self.hop_budget < 0:
            raise ValueError("hop_budget must be non-negative")
        if self.selections_per_hop < 1:
            raise ValueError("selections_per_hop must be positive")


@dataclass(frozen=True)
class WorldGrowthReceipt:
    hop: int
    source: str
    target: str
    edge_family: str
    relation: str
    priority: int
    cycle: bool


@dataclass(frozen=True)
class WorldWalkResult:
    schema_version: str
    seed: str
    hop_budget: int
    actual_hops: int
    nodes: tuple[str, ...]
    receipts: tuple[WorldGrowthReceipt, ...]
    semantic_promotion: bool = False
    live_publication_performed: bool = False


ExpandFn = Callable[[str], Iterable[EdgeCandidate]]


def _candidate_key(candidate: EdgeCandidate) -> tuple[int, str, str, str, str]:
    return (
        -candidate.priority,
        candidate.edge_family,
        candidate.relation,
        candidate.source,
        candidate.target,
    )


def _validated_candidates(source: str, candidates: Iterable[EdgeCandidate]) -> list[EdgeCandidate]:
    validated: list[EdgeCandidate] = []
    for candidate in candidates:
        if candidate.source != source:
            raise ValueError("expanded candidate source must match the current locus")
        if not candidate.target:
            raise ValueError("candidate target must be non-empty")
        if not candidate.edge_family:
            raise ValueError("candidate edge_family must be non-empty")
        if not candidate.relation:
            raise ValueError("candidate relation must be non-empty")
        validated.append(candidate)
    return sorted(validated, key=_candidate_key)


def walk_world(*, seed: str, policy: WorldWalkPolicy, expand: ExpandFn) -> WorldWalkResult:
    """Grow a bounded, deterministic local inquiry bucket.

    This runtime accepts already-produced candidate edges. It does not fetch,
    crawl, publish, or promote semantics. Each selected extension is retained
    as an append-only receipt, including revisits/cycles.
    """

    if not seed:
        raise ValueError("seed must be non-empty")

    nodes: list[str] = [seed]
    seen = {seed}
    receipts: list[WorldGrowthReceipt] = []
    frontier: list[str] = [seed]

    while frontier and len(receipts) < policy.hop_budget:
        source = frontier.pop(0)
        candidates = _validated_candidates(source, expand(source))
        selected = candidates[: policy.selections_per_hop]
        for candidate in selected:
            if len(receipts) >= policy.hop_budget:
                break
            is_cycle = candidate.target in seen
            receipts.append(
                WorldGrowthReceipt(
                    hop=len(receipts) + 1,
                    source=candidate.source,
                    target=candidate.target,
                    edge_family=candidate.edge_family,
                    relation=candidate.relation,
                    priority=candidate.priority,
                    cycle=is_cycle,
                )
            )
            if not is_cycle:
                seen.add(candidate.target)
                nodes.append(candidate.target)
                frontier.append(candidate.target)

    return WorldWalkResult(
        schema_version=WORLD_WALK_SCHEMA_VERSION,
        seed=seed,
        hop_budget=policy.hop_budget,
        actual_hops=len(receipts),
        nodes=tuple(nodes),
        receipts=tuple(receipts),
    )


def _receipt_dict(receipt: WorldGrowthReceipt) -> dict[str, object]:
    return {
        "hop": receipt.hop,
        "source": receipt.source,
        "target": receipt.target,
        "edge_family": receipt.edge_family,
        "relation": receipt.relation,
        "priority": receipt.priority,
        "cycle": receipt.cycle,
    }


def _canonical_json_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_publishable_bucket_manifest(
    result: WorldWalkResult,
    *,
    selected_node_ids: set[str] | frozenset[str],
    parent_bucket_cids: Sequence[str] = (),
    compiler_version: str,
) -> dict[str, object]:
    """Project a local walk into a candidate-only immutable-package manifest.

    The manifest deliberately contains no browsing/Reading-Trail history. It is
    a logical packaging target for a later Kant/eRDFa/IPFS adapter; this
    function performs no external publication and does not manufacture a CID.
    """

    result_nodes = set(result.nodes)
    selected = sorted(node for node in selected_node_ids if node in result_nodes)
    selected_set = set(selected)
    selected_receipts = [
        _receipt_dict(receipt)
        for receipt in result.receipts
        if receipt.source in selected_set and receipt.target in selected_set
    ]
    shard_identity_digest = _canonical_json_digest(
        {
            "seed": result.seed,
            "selected_node_ids": selected,
            "typed_edge_receipts": selected_receipts,
        }
    )

    payload: dict[str, object] = {
        "schema_version": WORLD_BUCKET_SCHEMA_VERSION,
        "seed": result.seed,
        "walk_schema_version": result.schema_version,
        "hop_budget": result.hop_budget,
        "actual_hop_count": result.actual_hops,
        "selected_node_ids": selected,
        "typed_edge_receipts": selected_receipts,
        "parent_bucket_cids": sorted(set(parent_bucket_cids)),
        "compiler_version": compiler_version,
        "candidate_only": True,
        "semantic_promotion": False,
        "live_ipfs_publication_performed": False,
        "publication_projection_is_browsing_history": False,
        "packaging": {
            "target": "kant-erdfa-shardset",
            "manifest_format": "cbor-compatible-logical-envelope",
            "content_addressing": "sha256-now-cid-later",
            "logical_shard_id": f"world-bucket:{shard_identity_digest[:24]}",
            "sink_refs": [],
        },
    }
    payload["content_digest"] = "sha256:" + _canonical_json_digest(payload)
    return payload
