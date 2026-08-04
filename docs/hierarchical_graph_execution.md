# Persistent hierarchical graph execution

The canonical semantic object remains the document graph. The hierarchy in this
module is a bounded physical execution carrier over that graph.

The implementation contract is:

> worker-resident text fibres construct immutable mini-graphs; parent jobs build
> midi- and mega-graph overlays over child graph references; nonlocal semantic
> dependencies are placed at the lowest hierarchy node containing all required
> evidence; no parent physically reconstructs settled descendant interiors.

## Carrier parameters

For primitive unit count `n`, leaf capacity `b`, hierarchy arity `a`, and worker
budget `W`:

```text
leaf_count = ceil(n / b)
depth      = ceil(log_a(leaf_count))
```

The initial document-0008 experiment uses:

```text
b = 4096
a = 4
W = 4
```

`HierarchyPlan` constructs globally coordinated half-open carrier intervals. A
full sixteen-leaf plan therefore contains:

```text
16 leaves -> 4 branches -> 1 root
```

Internal groups may be partial. `hierarchy_node_count()` computes the exact node
count rather than assuming every level is full.

## Physical graph node

`PersistentGraphNode` stores:

```text
child_graph_refs
introduced_vertex_refs
introduced_edge_refs
revision_transition_refs
GraphInterface
coverage certificate
revision
```

The logical graph denoted by a node includes its descendants, but the physical
node stores only immutable child references and structure introduced at that
level. `descendant_bytes_reconstructed` is an explicit complexity receipt. It
must normally remain zero.

A `GraphInterface` exposes only the subtree surfaces that may interact outside
the child carrier:

```text
boundary vertices
dependency keys
recurrence keys
constraint frontier
unresolved demands
index references
```

This interface is not a lossy replacement for the mini-graph. The child graph
remains durable and addressable by `graph_ref`; the interface is the efficient
input surface for its parent.

## Lowest sufficient carrier

For a job whose evidence support lies in source offsets `I`, execution is placed
at the lowest node covering every supporting leaf:

```text
node(job) = LCA(leaves(I))
```

Local extraction remains at a leaf. A relation crossing neighbouring leaves is
solved at their branch. A document-wide dependency rises to the root. The tree
provides bounded physical aggregation while the semantic dependency graph
creates targeted reconciliation jobs.

## Dynamic readiness

`HierarchicalGraphCoordinator` begins with all leaves ready. Completing a node:

1. installs an immutable overlay;
2. records work/interface/cross-edge/demand/revision metrics;
3. updates its parent's completed-child coverage;
4. enqueues the parent only when its declared child barrier is complete.

The existing `BoundedDocumentScheduler` can therefore execute leaves, branches,
and the root through one work-conserving pool. Workers are not permanently
assigned to a hierarchy level.

## Fixed point

A hierarchy node may complete only with a certificate declaring:

```text
all required children complete
local fixed point reached
no locally satisfiable unresolved demands
```

The hierarchy reaches its root fixed point when every required node has
completed, no ready hierarchy jobs remain, and the root certificate is complete.
This certificate complements rather than replaces the canonical PNF fixed-point
certificate.

## Complexity target

Reading the input already costs `Omega(n)`, so the compilation target cannot be
strictly sublinear. The target is:

```text
T_local = Theta(n)
T_total = Theta(n + m + d + r)
```

where:

- `m` is actual local and cross-carrier semantic edge work;
- `d` is actual demand work;
- `r` is actual revision work.

With bounded interface size and sparse semantic dependencies, these terms remain
linear in document size.

The accidental repeated-prefix pattern is:

```text
b + 2b + 3b + ... + Lb = Theta(n^2 / b)
```

The persistent hierarchy instead solves every primitive item once at its lowest
sufficient carrier and charges internal nodes for interface and cross-child work,
not for replaying descendant carrier size.

`HierarchyComplexityReceipt` records:

```text
primitive units
leaf count and node count
interface reference work
cross-relation work
demand work
revision work
descendant bytes reconstructed
```

`document_complexity_model.py` declares target and anti-pattern contracts for:

- parser annotation;
- parser-observation projection;
- proposal generation;
- streaming closure;
- hierarchical reduction;
- constraint assessment;
- refinement;
- demand derivation;
- PostgreSQL persistence.

## Immediate projection correction

The document-0008 trace showed fixed 4,096-atom batches slowing from about 83.6
to 47.6 atoms per second. Inspection found a direct quadratic hotspot: every
semantic atom linearly searched the complete parser-token tuple for an exact
span match.

`indexed_projection_execution.py` replaces that scan with an immutable span-keyed
index while preserving the original projection function as
`_serial_semantic_annotation_layer` for parity comparison.

At every 4,096-atom boundary the indexed path reports:

```text
batch_elapsed_ms
last_batch_size
process_tree_rss_bytes
gc_collection_counts
lookup_operations
retained_object_counts
```

The indexed strategy is enabled by default and can be disabled for parity
diagnosis:

```text
SENSIBLAW_INDEXED_SEMANTIC_PROJECTION=0
```

## Configuration

```text
SENSIBLAW_HIERARCHY_LEAF_CAPACITY=4096
SENSIBLAW_HIERARCHY_ARITY=4
SENSIBLAW_INDEXED_SEMANTIC_PROJECTION=1
```

These values select an execution policy only. They cannot alter source identity,
canonical coordinates, PNF reduction rules, or legal/semantic authority.

## Remaining integration boundary

The hierarchy algebra, coordinator, dynamic readiness, complexity receipts,
indexed projection, and parity surfaces now exist. The next production step is
to make semantic projection emit durable leaf graph revisions and route their
interfaces through the coordinator. Constraint/refinement and persistence must
then consume revision references rather than flattened complete graph
generations.
