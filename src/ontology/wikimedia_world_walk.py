from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence


WORLD_BUCKET_SCHEMA_VERSION = "sl.wikimedia_world_bucket.v0_1"
WORLD_WALK_SCHEMA_VERSION = "sl.wikimedia_world_walk.v0_1"
DEFAULT_WIKIDATA_WORLD_PROPERTIES = ("P31", "P279", "P361", "P527")
ONTOLOGY_WORLD_PROPERTIES = frozenset(DEFAULT_WIKIDATA_WORLD_PROPERTIES)


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


@dataclass(frozen=True)
class WorldBucketProjection:
    """Typed candidate publication projection for a local world bucket.

    This is a logical package description only.  It deliberately contains no
    Reading Trail / browsing-history coordinate and performs no live
    publication.  The digest is computed over typed length-prefixed fields,
    not a JSON serialization.
    """

    schema_version: str
    seed: str
    walk_schema_version: str
    hop_budget: int
    actual_hop_count: int
    selected_node_ids: tuple[str, ...]
    typed_edge_receipts: tuple[WorldGrowthReceipt, ...]
    parent_bucket_cids: tuple[str, ...]
    compiler_version: str
    candidate_only: bool
    semantic_promotion: bool
    live_ipfs_publication_performed: bool
    publication_projection_is_browsing_history: bool
    packaging_target: str
    manifest_format: str
    content_addressing: str
    logical_shard_id: str
    sink_refs: tuple[str, ...]
    content_digest: str


ExpandFn = Callable[[str], Iterable[EdgeCandidate]]


def _candidate_key(candidate: EdgeCandidate) -> tuple[int, str, str, str, str]:
    return (
        -candidate.priority,
        candidate.edge_family,
        candidate.relation,
        candidate.source,
        candidate.target,
    )


def _is_qid(text: str) -> bool:
    if len(text) < 2 or text[0] != "Q":
        return False
    return all("0" <= character <= "9" for character in text[1:])


def _extract_entity_qid(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("http://www.wikidata.org/entity/"):
            text = text.rsplit("/", 1)[-1]
        return text if _is_qid(text) else None
    if isinstance(value, dict):
        for key in ("id", "value"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                qid = _extract_entity_qid(candidate)
                if qid is not None:
                    return qid
    return None


def edge_candidates_from_wikidata_bundles(
    bundles: Iterable[object],
    *,
    property_filter: Sequence[str] = DEFAULT_WIKIDATA_WORLD_PROPERTIES,
) -> list[EdgeCandidate]:
    """Compile retained Wikidata StatementBundle-shaped rows into world edges.

    This is deliberately narrower than parsing Wikidata again: callers pass the
    existing retained bundle objects. Only entity-valued statements on the
    explicit property filter become candidates. Non-entity values are ignored
    rather than guessed into identities.
    """

    allowed = set(property_filter)
    edges: list[EdgeCandidate] = []
    for bundle in bundles:
        subject = str(getattr(bundle, "subject", "")).strip()
        property_id = str(getattr(bundle, "property", "")).strip()
        if not subject or property_id not in allowed:
            continue
        target = _extract_entity_qid(getattr(bundle, "value", None))
        if target is None:
            continue
        family = (
            "wikidata_ontology"
            if property_id in ONTOLOGY_WORLD_PROPERTIES
            else "wikidata_property"
        )
        priority = 20 if family == "wikidata_ontology" else 10
        edges.append(
            EdgeCandidate(
                source=subject,
                target=target,
                edge_family=family,
                relation=property_id,
                priority=priority,
            )
        )
    return sorted(edges, key=lambda edge: (edge.relation, edge.target, edge.source))


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


def _feed_receipt(hasher: "hashlib._Hash", receipt: WorldGrowthReceipt) -> None:
    _feed_int(hasher, "hop", receipt.hop)
    _feed_text(hasher, "source", receipt.source)
    _feed_text(hasher, "target", receipt.target)
    _feed_text(hasher, "edge_family", receipt.edge_family)
    _feed_text(hasher, "relation", receipt.relation)
    _feed_int(hasher, "priority", receipt.priority)
    _feed_bool(hasher, "cycle", receipt.cycle)


def _projection_identity_digest(
    *,
    seed: str,
    selected_node_ids: tuple[str, ...],
    typed_edge_receipts: tuple[WorldGrowthReceipt, ...],
) -> str:
    hasher = hashlib.sha256()
    _feed_text(hasher, "seed", seed)
    for node_id in selected_node_ids:
        _feed_text(hasher, "selected_node", node_id)
    for receipt in typed_edge_receipts:
        _feed_receipt(hasher, receipt)
    return hasher.hexdigest()


def _projection_content_digest(
    *,
    result: WorldWalkResult,
    selected_node_ids: tuple[str, ...],
    typed_edge_receipts: tuple[WorldGrowthReceipt, ...],
    parent_bucket_cids: tuple[str, ...],
    compiler_version: str,
    logical_shard_id: str,
) -> str:
    hasher = hashlib.sha256()
    _feed_text(hasher, "schema_version", WORLD_BUCKET_SCHEMA_VERSION)
    _feed_text(hasher, "seed", result.seed)
    _feed_text(hasher, "walk_schema_version", result.schema_version)
    _feed_int(hasher, "hop_budget", result.hop_budget)
    _feed_int(hasher, "actual_hop_count", result.actual_hops)
    for node_id in selected_node_ids:
        _feed_text(hasher, "selected_node", node_id)
    for receipt in typed_edge_receipts:
        _feed_receipt(hasher, receipt)
    for parent in parent_bucket_cids:
        _feed_text(hasher, "parent_bucket_cid", parent)
    _feed_text(hasher, "compiler_version", compiler_version)
    _feed_bool(hasher, "candidate_only", True)
    _feed_bool(hasher, "semantic_promotion", False)
    _feed_bool(hasher, "live_ipfs_publication_performed", False)
    _feed_bool(hasher, "publication_projection_is_browsing_history", False)
    _feed_text(hasher, "packaging_target", "kant-erdfa-shardset")
    _feed_text(hasher, "manifest_format", "cbor-compatible-logical-envelope")
    _feed_text(hasher, "content_addressing", "sha256-now-cid-later")
    _feed_text(hasher, "logical_shard_id", logical_shard_id)
    return hasher.hexdigest()


def build_publishable_bucket_manifest(
    result: WorldWalkResult,
    *,
    selected_node_ids: set[str] | frozenset[str],
    parent_bucket_cids: Sequence[str] = (),
    compiler_version: str,
) -> WorldBucketProjection:
    """Project a local walk into a candidate-only typed logical package.

    The projection deliberately contains no browsing/Reading-Trail history. It
    is a logical target for a later Kant/eRDFa/IPFS adapter; this function
    performs no external publication and does not manufacture a CID.
    """

    result_nodes = set(result.nodes)
    selected = tuple(sorted(node for node in selected_node_ids if node in result_nodes))
    selected_set = set(selected)
    selected_receipts = tuple(
        receipt
        for receipt in result.receipts
        if receipt.source in selected_set and receipt.target in selected_set
    )
    parents = tuple(sorted(set(parent_bucket_cids)))
    shard_identity_digest = _projection_identity_digest(
        seed=result.seed,
        selected_node_ids=selected,
        typed_edge_receipts=selected_receipts,
    )
    logical_shard_id = f"world-bucket:{shard_identity_digest[:24]}"
    content_digest = _projection_content_digest(
        result=result,
        selected_node_ids=selected,
        typed_edge_receipts=selected_receipts,
        parent_bucket_cids=parents,
        compiler_version=compiler_version,
        logical_shard_id=logical_shard_id,
    )
    return WorldBucketProjection(
        schema_version=WORLD_BUCKET_SCHEMA_VERSION,
        seed=result.seed,
        walk_schema_version=result.schema_version,
        hop_budget=result.hop_budget,
        actual_hop_count=result.actual_hops,
        selected_node_ids=selected,
        typed_edge_receipts=selected_receipts,
        parent_bucket_cids=parents,
        compiler_version=compiler_version,
        candidate_only=True,
        semantic_promotion=False,
        live_ipfs_publication_performed=False,
        publication_projection_is_browsing_history=False,
        packaging_target="kant-erdfa-shardset",
        manifest_format="cbor-compatible-logical-envelope",
        content_addressing="sha256-now-cid-later",
        logical_shard_id=logical_shard_id,
        sink_refs=(),
        content_digest="sha256:" + content_digest,
    )
