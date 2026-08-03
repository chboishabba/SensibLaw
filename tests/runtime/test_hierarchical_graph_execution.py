from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.runtime.bounded_document_scheduler import BoundedDocumentScheduler
from src.runtime.document_execution_policy import (
    DocumentExecutionPolicy,
    ResourceSnapshot,
)
from src.runtime.hierarchical_graph_execution import (
    GraphInterface,
    HierarchicalGraphCoordinator,
    HierarchyCoverageCertificate,
    HierarchyCoverageState,
    HierarchyDelta,
    HierarchyNodeKind,
    HierarchyPlan,
)


MIB = 1024 * 1024


def _policy() -> DocumentExecutionPolicy:
    return DocumentExecutionPolicy(
        worker_budget=4,
        max_in_flight_jobs=4,
        queue_limit_bytes=64 * MIB,
        soft_memory_limit_bytes=512 * MIB,
        hard_memory_limit_bytes=768 * MIB,
        recovery_target_bytes=384 * MIB,
    )


def _completed_delta(coordinator: HierarchicalGraphCoordinator, job):
    node = coordinator.nodes[job.node_ref]
    children = coordinator.plan.children_by_node.get(job.node_ref, ())
    interface = GraphInterface(
        boundary_vertex_refs=(f"boundary:{job.node_ref}",),
        dependency_keys=(f"dependency:{job.node_ref}",),
        unresolved_demand_refs=(),
        index_refs=(f"index:{job.node_ref}",),
    )
    work_units = (
        node.carrier.size
        if node.kind is HierarchyNodeKind.LEAF
        else sum(
            coordinator.nodes[child].interface.reference_count for child in children
        )
    )
    return HierarchyDelta(
        node_ref=job.node_ref,
        introduced_vertex_refs=(f"vertex:{job.node_ref}",),
        introduced_edge_refs=(
            ()
            if node.kind is HierarchyNodeKind.LEAF
            else (f"cross-edge:{job.node_ref}",)
        ),
        interface=interface,
        coverage=HierarchyCoverageCertificate(
            node_ref=job.node_ref,
            state=HierarchyCoverageState.COMPLETE,
            completed_child_refs=tuple(sorted(children)),
            required_child_refs=tuple(sorted(children)),
            locally_fixed_point=True,
        ),
        work_units=work_units,
        output_bytes=128,
        descendant_bytes_reconstructed=0,
    )


def _solve_one_level(
    coordinator: HierarchicalGraphCoordinator,
    jobs,
):
    unlocked = ()
    for scheduled in jobs:
        unlocked = coordinator.admit(
            scheduled.payload,
            _completed_delta(coordinator, scheduled.payload),
        )
    return unlocked


def test_plan_builds_bounded_four_ary_hierarchy_and_lca_placement() -> None:
    plan = HierarchyPlan.build(
        document_ref="document:hierarchy",
        primitive_unit_count=16 * 4096,
        leaf_capacity=4096,
        arity=4,
        unit="atoms",
    )

    assert len(plan.leaf_refs) == 16
    assert plan.depth == 2
    assert plan.node_count == 21
    assert plan.node_count <= plan.relaxed_node_bound
    assert plan.lowest_sufficient_node_for_offsets((1, 4095)) == (plan.leaf_refs[0])

    same_branch = plan.lowest_sufficient_node_for_offsets((1, 4 * 4096 - 1))
    assert plan.level_of(same_branch) == 1

    document_wide = plan.lowest_sufficient_node_for_offsets((1, 15 * 4096))
    assert document_wide == plan.root_ref


def test_workers_solve_leaves_then_unlock_branches_and_root() -> None:
    plan = HierarchyPlan.build(
        document_ref="document:hierarchy",
        primitive_unit_count=16 * 4096,
        leaf_capacity=4096,
        arity=4,
        unit="atoms",
    )
    coordinator = HierarchicalGraphCoordinator(plan)
    execution_levels: list[int] = []

    def execute(job):
        execution_levels.append(job.level)
        return _completed_delta(coordinator, job)

    def admit(scheduled, delta):
        return coordinator.admit(scheduled.payload, delta)

    def sample(
        queued: int,
        pending: int,
        in_flight: int,
    ) -> ResourceSnapshot:
        return ResourceSnapshot(
            rss_bytes=128 * MIB,
            process_tree_rss_bytes=128 * MIB,
            queued_bytes=queued,
            pending_jobs=pending,
            in_flight_jobs=in_flight,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        scheduler = BoundedDocumentScheduler(
            executor=pool,
            execute=execute,
            admit=admit,
            sample_resources=sample,
            compact=lambda: None,
            policy=_policy(),
        )
        scheduler.extend(coordinator.ready_jobs())
        receipt = scheduler.run()

    assert receipt.jobs_completed == plan.node_count
    assert execution_levels.count(0) == 16
    assert execution_levels.count(1) == 4
    assert execution_levels.count(2) == 1
    assert coordinator.fixed_point_reached is True
    assert coordinator.fixed_point_certificate()["waiting_node_refs"] == []


def test_parent_graphs_reference_children_without_flattening_descendants() -> None:
    plan = HierarchyPlan.build(
        document_ref="document:hierarchy",
        primitive_unit_count=4 * 4096,
        leaf_capacity=4096,
        arity=4,
        unit="atoms",
    )
    coordinator = HierarchicalGraphCoordinator(plan)
    root_jobs = _solve_one_level(
        coordinator,
        coordinator.ready_jobs(),
    )

    assert len(root_jobs) == 1
    root_job = root_jobs[0]
    assert root_job.payload.estimated_compute_units == 12
    coordinator.admit(
        root_job.payload,
        _completed_delta(coordinator, root_job.payload),
    )

    root = coordinator.nodes[plan.root_ref]
    child_graph_refs = tuple(
        sorted(coordinator.nodes[child].graph_ref for child in plan.leaf_refs)
    )
    complexity = coordinator.complexity_receipt()

    assert root.child_graph_refs == child_graph_refs
    assert len(root.introduced_vertex_refs) == 1
    assert len(root.introduced_edge_refs) == 1
    assert complexity.flattening_free is True
    assert complexity.descendant_bytes_reconstructed == 0
    assert complexity.total_work_units == 4 * 4096 + 12


def test_revision_cone_reopens_leaf_and_invalidates_only_ancestors() -> None:
    plan = HierarchyPlan.build(
        document_ref="document:hierarchy-revision",
        primitive_unit_count=4 * 4096,
        leaf_capacity=4096,
        arity=4,
        unit="atoms",
    )
    coordinator = HierarchicalGraphCoordinator(plan)
    root_jobs = _solve_one_level(
        coordinator,
        coordinator.ready_jobs(),
    )
    root_job = root_jobs[0]
    coordinator.admit(
        root_job.payload,
        _completed_delta(coordinator, root_job.payload),
    )
    prior_root_ref = coordinator.nodes[plan.root_ref].graph_ref
    unchanged_leaf_refs = {
        leaf_ref: coordinator.nodes[leaf_ref].graph_ref
        for leaf_ref in plan.leaf_refs[1:]
    }

    reopened = coordinator.invalidate_node(
        plan.leaf_refs[0],
        locally_satisfiable_demand_refs=("demand:cross-leaf",),
    )

    assert len(reopened) == 1
    assert reopened[0].payload.node_ref == plan.leaf_refs[0]
    assert coordinator.fixed_point_reached is False
    revised_root_jobs = coordinator.admit(
        reopened[0].payload,
        _completed_delta(coordinator, reopened[0].payload),
    )
    assert len(revised_root_jobs) == 1
    coordinator.admit(
        revised_root_jobs[0].payload,
        _completed_delta(
            coordinator,
            revised_root_jobs[0].payload,
        ),
    )

    assert coordinator.fixed_point_reached is True
    assert coordinator.nodes[plan.root_ref].graph_ref != prior_root_ref
    assert {
        leaf_ref: coordinator.nodes[leaf_ref].graph_ref
        for leaf_ref in plan.leaf_refs[1:]
    } == unchanged_leaf_refs


def test_parent_waits_while_leaf_jobs_are_ready() -> None:
    plan = HierarchyPlan.build(
        document_ref="document:hierarchy",
        primitive_unit_count=4 * 4096,
        leaf_capacity=4096,
        arity=4,
    )
    coordinator = HierarchicalGraphCoordinator(plan)
    root = coordinator.nodes[plan.root_ref]
    leaf_jobs = coordinator.ready_jobs()

    assert root.coverage is not None
    assert root.coverage.state is HierarchyCoverageState.WAITING
    assert len(leaf_jobs) == 4
    assert all(job.payload.level == 0 for job in leaf_jobs)
