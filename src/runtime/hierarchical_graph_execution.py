"""Persistent mini/midi/mega graph hierarchy for bounded document execution.

The hierarchy is a physical execution carrier. It does not replace the canonical
PNF document graph. Leaves own bounded source intervals. Internal nodes reference
immutable child graph revisions and introduce only cross-child structure,
indexes, revisions, and unresolved demands.

Logical descendant unions are never instructions to flatten child interiors into
new Python collections.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import ceil
from typing import Iterable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.runtime.bounded_document_scheduler import ScheduledJob, WorkClass


class HierarchyNodeKind(StrEnum):
    LEAF = "leaf"
    BRANCH = "branch"
    ROOT = "root"


class HierarchyCoverageState(StrEnum):
    WAITING = "waiting"
    READY = "ready"
    COMPLETE = "complete"


@dataclass(frozen=True, order=True)
class CarrierInterval:
    """Half-open globally coordinated carrier interval."""

    start: int
    end: int
    unit: str = "items"

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("carrier start must be non-negative")
        if self.end <= self.start:
            raise ValueError("carrier end must be greater than start")
        if not self.unit:
            raise ValueError("carrier unit is required")

    @property
    def size(self) -> int:
        return self.end - self.start

    def contains(self, offset: int) -> bool:
        return self.start <= offset < self.end

    def covers(self, other: "CarrierInterval") -> bool:
        return self.start <= other.start and other.end <= self.end

    def to_dict(self) -> dict[str, object]:
        return {
            "start": self.start,
            "end": self.end,
            "unit": self.unit,
            "size": self.size,
        }


@dataclass(frozen=True)
class GraphInterface:
    """Externally visible interface of one immutable graph node."""

    boundary_vertex_refs: tuple[str, ...] = ()
    dependency_keys: tuple[str, ...] = ()
    recurrence_keys: tuple[str, ...] = ()
    constraint_frontier_refs: tuple[str, ...] = ()
    unresolved_demand_refs: tuple[str, ...] = ()
    index_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for refs in self._all_sequences():
            if refs != tuple(sorted(set(refs))):
                raise ValueError(
                    "graph interface references must be sorted and unique"
                )

    def _all_sequences(self) -> tuple[tuple[str, ...], ...]:
        return (
            self.boundary_vertex_refs,
            self.dependency_keys,
            self.recurrence_keys,
            self.constraint_frontier_refs,
            self.unresolved_demand_refs,
            self.index_refs,
        )

    @property
    def reference_count(self) -> int:
        return sum(len(refs) for refs in self._all_sequences())

    def merged(self, *others: "GraphInterface") -> "GraphInterface":
        rows = (self, *others)

        def union(name: str) -> tuple[str, ...]:
            return tuple(
                sorted(
                    {
                        ref
                        for row in rows
                        for ref in getattr(row, name)
                    }
                )
            )

        return GraphInterface(
            boundary_vertex_refs=union("boundary_vertex_refs"),
            dependency_keys=union("dependency_keys"),
            recurrence_keys=union("recurrence_keys"),
            constraint_frontier_refs=union("constraint_frontier_refs"),
            unresolved_demand_refs=union("unresolved_demand_refs"),
            index_refs=union("index_refs"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "boundary_vertex_refs": list(self.boundary_vertex_refs),
            "dependency_keys": list(self.dependency_keys),
            "recurrence_keys": list(self.recurrence_keys),
            "constraint_frontier_refs": list(
                self.constraint_frontier_refs
            ),
            "unresolved_demand_refs": list(
                self.unresolved_demand_refs
            ),
            "index_refs": list(self.index_refs),
            "reference_count": self.reference_count,
        }


@dataclass(frozen=True)
class HierarchyCoverageCertificate:
    node_ref: str
    state: HierarchyCoverageState
    completed_child_refs: tuple[str, ...]
    required_child_refs: tuple[str, ...]
    locally_fixed_point: bool
    unresolved_locally_satisfiable_demands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for refs in (
            self.completed_child_refs,
            self.required_child_refs,
            self.unresolved_locally_satisfiable_demands,
        ):
            if refs != tuple(sorted(set(refs))):
                raise ValueError(
                    "coverage references must be sorted and unique"
                )

    @property
    def complete(self) -> bool:
        return (
            self.state is HierarchyCoverageState.COMPLETE
            and self.completed_child_refs == self.required_child_refs
            and self.locally_fixed_point
            and not self.unresolved_locally_satisfiable_demands
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "node_ref": self.node_ref,
            "state": self.state.value,
            "completed_child_refs": list(self.completed_child_refs),
            "required_child_refs": list(self.required_child_refs),
            "locally_fixed_point": self.locally_fixed_point,
            "unresolved_locally_satisfiable_demands": list(
                self.unresolved_locally_satisfiable_demands
            ),
            "complete": self.complete,
        }


@dataclass(frozen=True)
class PersistentGraphNode:
    """Physical graph node: child refs plus structure added at this level."""

    document_ref: str
    node_ref: str
    level: int
    kind: HierarchyNodeKind
    carrier: CarrierInterval
    child_graph_refs: tuple[str, ...] = ()
    introduced_vertex_refs: tuple[str, ...] = ()
    introduced_edge_refs: tuple[str, ...] = ()
    revision_transition_refs: tuple[str, ...] = ()
    interface: GraphInterface = GraphInterface()
    revision: int = 0
    coverage: HierarchyCoverageCertificate | None = None

    def __post_init__(self) -> None:
        if not self.document_ref or not self.node_ref:
            raise ValueError("document_ref and node_ref are required")
        if self.level < 0 or self.revision < 0:
            raise ValueError("level and revision must be non-negative")
        for refs in (
            self.child_graph_refs,
            self.introduced_vertex_refs,
            self.introduced_edge_refs,
            self.revision_transition_refs,
        ):
            if refs != tuple(sorted(set(refs))):
                raise ValueError(
                    "graph node references must be sorted and unique"
                )

    @property
    def graph_ref(self) -> str:
        digest = canonical_sha256(self.identity_payload())
        return f"hierarchical-graph:{digest}"

    @property
    def newly_materialized_reference_count(self) -> int:
        return (
            len(self.introduced_vertex_refs)
            + len(self.introduced_edge_refs)
            + len(self.revision_transition_refs)
            + self.interface.reference_count
        )

    def identity_payload(self) -> dict[str, object]:
        return {
            "document_ref": self.document_ref,
            "node_ref": self.node_ref,
            "level": self.level,
            "kind": self.kind.value,
            "carrier": self.carrier.to_dict(),
            "child_graph_refs": list(self.child_graph_refs),
            "introduced_vertex_refs": list(
                self.introduced_vertex_refs
            ),
            "introduced_edge_refs": list(self.introduced_edge_refs),
            "revision_transition_refs": list(
                self.revision_transition_refs
            ),
            "interface": self.interface.to_dict(),
            "revision": self.revision,
            "coverage": (
                self.coverage.to_dict() if self.coverage else None
            ),
        }

    def overlay(self, delta: "HierarchyDelta") -> "PersistentGraphNode":
        if delta.node_ref != self.node_ref:
            raise ValueError("hierarchy delta belongs to another node")
        return replace(
            self,
            introduced_vertex_refs=tuple(
                sorted(
                    set(self.introduced_vertex_refs)
                    | set(delta.introduced_vertex_refs)
                )
            ),
            introduced_edge_refs=tuple(
                sorted(
                    set(self.introduced_edge_refs)
                    | set(delta.introduced_edge_refs)
                )
            ),
            revision_transition_refs=tuple(
                sorted(
                    set(self.revision_transition_refs)
                    | set(delta.revision_transition_refs)
                )
            ),
            interface=self.interface.merged(delta.interface),
            revision=self.revision + 1,
            coverage=delta.coverage or self.coverage,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **self.identity_payload(),
            "graph_ref": self.graph_ref,
        }


@dataclass(frozen=True)
class HierarchyJob:
    job_ref: str
    operator_ref: str
    node_ref: str
    level: int
    input_graph_refs: tuple[str, ...]
    input_revision_refs: tuple[str, ...]
    output_owner_keys: tuple[str, ...]
    estimated_compute_units: int
    estimated_peak_memory_bytes: int
    estimated_output_bytes: int

    def __post_init__(self) -> None:
        if not self.job_ref or not self.operator_ref or not self.node_ref:
            raise ValueError("hierarchy job identity is required")
        if self.level < 0:
            raise ValueError("hierarchy job level must be non-negative")
        for refs in (
            self.input_graph_refs,
            self.input_revision_refs,
            self.output_owner_keys,
        ):
            if refs != tuple(sorted(set(refs))):
                raise ValueError(
                    "hierarchy job references must be sorted and unique"
                )
        for value in (
            self.estimated_compute_units,
            self.estimated_peak_memory_bytes,
            self.estimated_output_bytes,
        ):
            if value < 0:
                raise ValueError(
                    "hierarchy job estimates must be non-negative"
                )


@dataclass(frozen=True)
class HierarchyDelta:
    node_ref: str
    introduced_vertex_refs: tuple[str, ...] = ()
    introduced_edge_refs: tuple[str, ...] = ()
    revision_transition_refs: tuple[str, ...] = ()
    interface: GraphInterface = GraphInterface()
    coverage: HierarchyCoverageCertificate | None = None
    work_units: int = 0
    input_bytes: int = 0
    output_bytes: int = 0
    descendant_bytes_reconstructed: int = 0

    def __post_init__(self) -> None:
        if not self.node_ref:
            raise ValueError("node_ref is required")
        for refs in (
            self.introduced_vertex_refs,
            self.introduced_edge_refs,
            self.revision_transition_refs,
        ):
            if refs != tuple(sorted(set(refs))):
                raise ValueError(
                    "hierarchy delta references must be sorted and unique"
                )
        for value in (
            self.work_units,
            self.input_bytes,
            self.output_bytes,
            self.descendant_bytes_reconstructed,
        ):
            if value < 0:
                raise ValueError(
                    "hierarchy delta metrics must be non-negative"
                )


@dataclass(frozen=True)
class HierarchyPlan:
    document_ref: str
    primitive_unit_count: int
    leaf_capacity: int
    arity: int
    root_ref: str
    node_refs_by_level: tuple[tuple[str, ...], ...]
    parent_by_node: Mapping[str, str]
    children_by_node: Mapping[str, tuple[str, ...]]
    carriers: Mapping[str, CarrierInterval]

    @classmethod
    def build(
        cls,
        *,
        document_ref: str,
        primitive_unit_count: int,
        leaf_capacity: int = 4096,
        arity: int = 4,
        unit: str = "items",
    ) -> "HierarchyPlan":
        if not document_ref:
            raise ValueError("document_ref is required")
        if primitive_unit_count < 1:
            raise ValueError("primitive_unit_count must be positive")
        if leaf_capacity < 1:
            raise ValueError("leaf_capacity must be positive")
        if arity < 2:
            raise ValueError("arity must be at least two")

        leaf_count = ceil(primitive_unit_count / leaf_capacity)
        carriers: dict[str, CarrierInterval] = {}
        levels: list[tuple[str, ...]] = []
        leaves: list[str] = []
        for index in range(leaf_count):
            carrier = CarrierInterval(
                index * leaf_capacity,
                min(
                    (index + 1) * leaf_capacity,
                    primitive_unit_count,
                ),
                unit,
            )
            node_ref = cls._node_ref(
                document_ref,
                level=0,
                ordinal=index,
                carrier=carrier,
            )
            carriers[node_ref] = carrier
            leaves.append(node_ref)
        levels.append(tuple(leaves))

        parent_by_node: dict[str, str] = {}
        children_by_node: dict[str, tuple[str, ...]] = {}
        current = tuple(leaves)
        level = 1
        while len(current) > 1:
            parents: list[str] = []
            for start in range(0, len(current), arity):
                children = current[start : start + arity]
                carrier = CarrierInterval(
                    carriers[children[0]].start,
                    carriers[children[-1]].end,
                    unit,
                )
                parent_ref = cls._node_ref(
                    document_ref,
                    level=level,
                    ordinal=start // arity,
                    carrier=carrier,
                )
                carriers[parent_ref] = carrier
                children_by_node[parent_ref] = tuple(children)
                for child_ref in children:
                    parent_by_node[child_ref] = parent_ref
                parents.append(parent_ref)
            current = tuple(parents)
            levels.append(current)
            level += 1

        root_ref = current[0]
        children_by_node.setdefault(root_ref, ())
        return cls(
            document_ref=document_ref,
            primitive_unit_count=primitive_unit_count,
            leaf_capacity=leaf_capacity,
            arity=arity,
            root_ref=root_ref,
            node_refs_by_level=tuple(levels),
            parent_by_node=parent_by_node,
            children_by_node=children_by_node,
            carriers=carriers,
        )

    @staticmethod
    def _node_ref(
        document_ref: str,
        *,
        level: int,
        ordinal: int,
        carrier: CarrierInterval,
    ) -> str:
        digest = canonical_sha256(
            {
                "document_ref": document_ref,
                "level": level,
                "ordinal": ordinal,
                "carrier": carrier.to_dict(),
            }
        )
        return f"hierarchy-node:{digest}"

    @property
    def leaf_refs(self) -> tuple[str, ...]:
        return self.node_refs_by_level[0]

    @property
    def depth(self) -> int:
        return len(self.node_refs_by_level) - 1

    @property
    def node_count(self) -> int:
        return sum(
            len(node_refs)
            for node_refs in self.node_refs_by_level
        )

    @property
    def relaxed_node_bound(self) -> float:
        leaf_count = len(self.leaf_refs)
        geometric = self.arity / (self.arity - 1) * leaf_count
        return geometric + self.depth

    def level_of(self, node_ref: str) -> int:
        for level, refs in enumerate(self.node_refs_by_level):
            if node_ref in refs:
                return level
        raise KeyError(node_ref)

    def leaf_for_offset(self, offset: int) -> str:
        if not 0 <= offset < self.primitive_unit_count:
            raise ValueError("offset outside document carrier")
        return self.leaf_refs[offset // self.leaf_capacity]

    def lowest_sufficient_node_for_offsets(
        self,
        offsets: Iterable[int],
    ) -> str:
        leaves = {
            self.leaf_for_offset(offset)
            for offset in offsets
        }
        if not leaves:
            raise ValueError(
                "at least one support offset is required"
            )
        return self.lowest_common_ancestor(tuple(sorted(leaves)))

    def lowest_common_ancestor(
        self,
        node_refs: Sequence[str],
    ) -> str:
        if not node_refs:
            raise ValueError("at least one node_ref is required")
        chains = [
            self._ancestor_chain(node_ref)
            for node_ref in node_refs
        ]
        common = set(chains[0]).intersection(
            *(set(chain) for chain in chains[1:])
        )
        if not common:
            raise ValueError(
                "nodes do not belong to one hierarchy"
            )
        return min(common, key=self.level_of)

    def _ancestor_chain(self, node_ref: str) -> tuple[str, ...]:
        if node_ref not in self.carriers:
            raise KeyError(node_ref)
        result = [node_ref]
        while result[-1] in self.parent_by_node:
            result.append(self.parent_by_node[result[-1]])
        return tuple(result)


@dataclass(frozen=True)
class HierarchyComplexityReceipt:
    primitive_units: int
    leaf_capacity: int
    arity: int
    leaf_count: int
    node_count: int
    relaxed_node_bound: float
    total_work_units: int
    interface_reference_work: int
    cross_relation_work: int
    demand_work: int
    revision_work: int
    descendant_bytes_reconstructed: int

    @property
    def flattening_free(self) -> bool:
        return self.descendant_bytes_reconstructed == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "primitive_units": self.primitive_units,
            "leaf_capacity": self.leaf_capacity,
            "arity": self.arity,
            "leaf_count": self.leaf_count,
            "node_count": self.node_count,
            "relaxed_node_bound": self.relaxed_node_bound,
            "node_bound_satisfied": (
                self.node_count <= self.relaxed_node_bound
            ),
            "total_work_units": self.total_work_units,
            "interface_reference_work": (
                self.interface_reference_work
            ),
            "cross_relation_work": self.cross_relation_work,
            "demand_work": self.demand_work,
            "revision_work": self.revision_work,
            "descendant_bytes_reconstructed": (
                self.descendant_bytes_reconstructed
            ),
            "flattening_free": self.flattening_free,
        }


@dataclass
class HierarchicalGraphCoordinator:
    """Unlock leaves, parents, and revision cones as coverage changes."""

    plan: HierarchyPlan
    nodes: dict[str, PersistentGraphNode] = field(
        default_factory=dict
    )
    _completed: set[str] = field(default_factory=set)
    _enqueued: set[str] = field(default_factory=set)
    _ready: deque[str] = field(default_factory=deque)
    _total_work_units: int = 0
    _interface_reference_work: int = 0
    _cross_relation_work: int = 0
    _demand_work: int = 0
    _revision_work: int = 0
    _descendant_bytes_reconstructed: int = 0

    def __post_init__(self) -> None:
        if not self.nodes:
            self._initialise_nodes()
        for leaf_ref in self.plan.leaf_refs:
            if leaf_ref not in self._completed:
                self._enqueue(leaf_ref)

    def _initialise_nodes(self) -> None:
        for level, node_refs in enumerate(
            self.plan.node_refs_by_level
        ):
            for node_ref in node_refs:
                children = self.plan.children_by_node.get(
                    node_ref,
                    (),
                )
                if level == 0:
                    kind = HierarchyNodeKind.LEAF
                elif node_ref == self.plan.root_ref:
                    kind = HierarchyNodeKind.ROOT
                else:
                    kind = HierarchyNodeKind.BRANCH
                child_graph_refs = tuple(
                    sorted(
                        self.nodes[child_ref].graph_ref
                        for child_ref in children
                    )
                )
                coverage = HierarchyCoverageCertificate(
                    node_ref=node_ref,
                    state=(
                        HierarchyCoverageState.READY
                        if not children
                        else HierarchyCoverageState.WAITING
                    ),
                    completed_child_refs=(),
                    required_child_refs=tuple(sorted(children)),
                    locally_fixed_point=False,
                )
                self.nodes[node_ref] = PersistentGraphNode(
                    document_ref=self.plan.document_ref,
                    node_ref=node_ref,
                    level=level,
                    kind=kind,
                    carrier=self.plan.carriers[node_ref],
                    child_graph_refs=child_graph_refs,
                    coverage=coverage,
                )

    def _enqueue(self, node_ref: str) -> None:
        if node_ref in self._enqueued:
            return
        self._enqueued.add(node_ref)
        self._ready.append(node_ref)

    def _estimated_compute_units(
        self,
        node_ref: str,
    ) -> int:
        node = self.nodes[node_ref]
        if node.kind is HierarchyNodeKind.LEAF:
            return node.carrier.size
        children = self.plan.children_by_node.get(node_ref, ())
        return max(
            1,
            sum(
                self.nodes[child].interface.reference_count
                for child in children
            ),
        )

    def ready_jobs(self) -> tuple[ScheduledJob[HierarchyJob], ...]:
        jobs: list[ScheduledJob[HierarchyJob]] = []
        while self._ready:
            node_ref = self._ready.popleft()
            node = self.nodes[node_ref]
            children = self.plan.children_by_node.get(node_ref, ())
            input_graph_refs = tuple(
                sorted(
                    self.nodes[child].graph_ref
                    for child in children
                )
            )
            input_revision_refs = tuple(
                sorted(
                    f"{child}:{self.nodes[child].revision}"
                    for child in children
                )
            )
            job_payload = {
                "node_ref": node_ref,
                "revision": node.revision,
                "input_graph_refs": input_graph_refs,
                "input_revision_refs": input_revision_refs,
            }
            job = HierarchyJob(
                job_ref=(
                    "hierarchy-job:"
                    + canonical_sha256(job_payload)
                ),
                operator_ref=(
                    "hierarchy.leaf.solve"
                    if node.kind is HierarchyNodeKind.LEAF
                    else "hierarchy.parent.reduce"
                ),
                node_ref=node_ref,
                level=node.level,
                input_graph_refs=input_graph_refs,
                input_revision_refs=input_revision_refs,
                output_owner_keys=(node_ref,),
                estimated_compute_units=(
                    self._estimated_compute_units(node_ref)
                ),
                estimated_peak_memory_bytes=0,
                estimated_output_bytes=0,
            )
            jobs.append(
                ScheduledJob(
                    job_ref=job.job_ref,
                    payload=job,
                    work_class=(
                        WorkClass.SEMANTIC_PRODUCER
                        if node.kind is HierarchyNodeKind.LEAF
                        else WorkClass.REDUCER
                    ),
                    priority=node.level,
                    criticality=node.level,
                )
            )
        return tuple(jobs)

    def admit(
        self,
        job: HierarchyJob,
        delta: HierarchyDelta,
    ) -> tuple[ScheduledJob[HierarchyJob], ...]:
        if job.node_ref != delta.node_ref:
            raise ValueError(
                "hierarchy result belongs to another job"
            )
        node = self.nodes[job.node_ref]
        expected_inputs = tuple(
            sorted(
                self.nodes[child].graph_ref
                for child in self.plan.children_by_node.get(
                    job.node_ref,
                    (),
                )
            )
        )
        if job.input_graph_refs != expected_inputs:
            raise ValueError(
                "hierarchy result is stale for current child revisions"
            )
        if delta.coverage is None or not delta.coverage.complete:
            raise ValueError(
                "hierarchy node may complete only with a fixed-point "
                "coverage certificate"
            )

        self.nodes[job.node_ref] = node.overlay(delta)
        self._completed.add(job.node_ref)
        self._enqueued.discard(job.node_ref)
        self._total_work_units += delta.work_units
        self._interface_reference_work += (
            delta.interface.reference_count
        )
        self._cross_relation_work += len(
            delta.introduced_edge_refs
        )
        self._demand_work += len(
            delta.interface.unresolved_demand_refs
        )
        self._revision_work += len(
            delta.revision_transition_refs
        )
        self._descendant_bytes_reconstructed += (
            delta.descendant_bytes_reconstructed
        )

        parent_ref = self.plan.parent_by_node.get(job.node_ref)
        if parent_ref is not None:
            self._refresh_parent(parent_ref)
        return self.ready_jobs()

    def _refresh_parent(self, parent_ref: str) -> None:
        children = self.plan.children_by_node[parent_ref]
        completed_children = tuple(
            sorted(set(children) & self._completed)
        )
        ready = completed_children == tuple(sorted(children))
        parent = self.nodes[parent_ref]
        coverage = HierarchyCoverageCertificate(
            node_ref=parent_ref,
            state=(
                HierarchyCoverageState.READY
                if ready
                else HierarchyCoverageState.WAITING
            ),
            completed_child_refs=completed_children,
            required_child_refs=tuple(sorted(children)),
            locally_fixed_point=False,
        )
        self.nodes[parent_ref] = replace(
            parent,
            child_graph_refs=tuple(
                sorted(
                    self.nodes[child].graph_ref
                    for child in children
                )
            ),
            coverage=coverage,
        )
        if ready:
            self._enqueue(parent_ref)

    def invalidate_node(
        self,
        node_ref: str,
        *,
        locally_satisfiable_demand_refs: Iterable[str] = (),
    ) -> tuple[ScheduledJob[HierarchyJob], ...]:
        """Re-open one node and invalidate ancestor certificates.

        Durable prior graph revisions remain addressable by their old graph refs;
        this coordinator only advances the active revision pointer.
        """

        if node_ref not in self.nodes:
            raise KeyError(node_ref)
        demands = tuple(
            sorted(set(locally_satisfiable_demand_refs))
        )
        node = self.nodes[node_ref]
        children = self.plan.children_by_node.get(node_ref, ())
        if children and not set(children).issubset(self._completed):
            raise ValueError(
                "cannot re-open a parent before child coverage completes"
            )

        self._completed.discard(node_ref)
        self._enqueued.discard(node_ref)
        self.nodes[node_ref] = replace(
            node,
            coverage=HierarchyCoverageCertificate(
                node_ref=node_ref,
                state=HierarchyCoverageState.READY,
                completed_child_refs=tuple(sorted(children)),
                required_child_refs=tuple(sorted(children)),
                locally_fixed_point=False,
                unresolved_locally_satisfiable_demands=demands,
            ),
        )
        self._enqueue(node_ref)

        ancestor = self.plan.parent_by_node.get(node_ref)
        while ancestor is not None:
            self._completed.discard(ancestor)
            self._enqueued.discard(ancestor)
            self._ready = deque(
                ref for ref in self._ready if ref != ancestor
            )
            self._refresh_parent(ancestor)
            ancestor = self.plan.parent_by_node.get(ancestor)
        return self.ready_jobs()

    @property
    def fixed_point_reached(self) -> bool:
        root = self.nodes[self.plan.root_ref]
        return (
            self.plan.root_ref in self._completed
            and root.coverage is not None
            and root.coverage.complete
            and not self._ready
        )

    def complexity_receipt(self) -> HierarchyComplexityReceipt:
        return HierarchyComplexityReceipt(
            primitive_units=self.plan.primitive_unit_count,
            leaf_capacity=self.plan.leaf_capacity,
            arity=self.plan.arity,
            leaf_count=len(self.plan.leaf_refs),
            node_count=self.plan.node_count,
            relaxed_node_bound=self.plan.relaxed_node_bound,
            total_work_units=self._total_work_units,
            interface_reference_work=(
                self._interface_reference_work
            ),
            cross_relation_work=self._cross_relation_work,
            demand_work=self._demand_work,
            revision_work=self._revision_work,
            descendant_bytes_reconstructed=(
                self._descendant_bytes_reconstructed
            ),
        )

    def fixed_point_certificate(self) -> dict[str, object]:
        root = self.nodes[self.plan.root_ref]
        waiting = tuple(
            sorted(
                node_ref
                for node_ref, node in self.nodes.items()
                if node.coverage is None
                or not node.coverage.complete
            )
        )
        return {
            "document_ref": self.plan.document_ref,
            "root_node_ref": self.plan.root_ref,
            "root_graph_ref": root.graph_ref,
            "root_coverage_complete": bool(
                root.coverage and root.coverage.complete
            ),
            "completed_node_count": len(self._completed),
            "node_count": self.plan.node_count,
            "waiting_node_refs": list(waiting),
            "ready_node_refs": list(self._ready),
            "fixed_point_reached": self.fixed_point_reached,
            "complexity": self.complexity_receipt().to_dict(),
        }


__all__ = [
    "CarrierInterval",
    "GraphInterface",
    "HierarchicalGraphCoordinator",
    "HierarchyComplexityReceipt",
    "HierarchyCoverageCertificate",
    "HierarchyCoverageState",
    "HierarchyDelta",
    "HierarchyJob",
    "HierarchyNodeKind",
    "HierarchyPlan",
    "PersistentGraphNode",
]
