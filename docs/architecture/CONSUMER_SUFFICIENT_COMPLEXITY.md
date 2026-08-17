# Consumer-sufficient runtime complexity

Exact Kolmogorov complexity is not a runtime metric: `K(x)` is uncomputable and
cannot be used as an empirical performance claim.  The ITIR/PNF optimization
boundary is instead a computable structural surrogate constrained by the formal
consumer-safety theorems.

For a represented carrier `X`, use an explicitly unit-normalised operational
cost such as

```text
Khat(X) = |nodes| + |edges| + |residuals| + |encoded units| + |boundary demands|.
```

Weights or physical units may be introduced by a benchmark, but incomparable
units must not be silently added.  `src/runtime/semantic_complexity_audit.py`
therefore exposes raw counts and a unit-weight reference projection rather than
claiming a universal information measure.

A smaller projection is admissible for consumer `C` only when all of the
following are established:

```text
C(X) = C(pi(X))
residual(X) = residual(pi(X))
provenance(X) = provenance(pi(X))
Khat(pi(X)) <= Khat(X).
```

A missing factorisation/provenance/residual premise is `indeterminate`; a cheap
destructive quotient is not an optimization certificate.

State complexity and transition complexity are distinct.  The preferred
transition contract is

```text
measured work <= |active frontier| + |dependency edges touched|,
```

not repeated work over the whole document or whole accumulated owner carrier.
`repeated_full_fibre_exposure()` makes this physical distinction explicit.  If
one proposal reaches one owner in each of eight waves, repeatedly scanning the
entire accumulated fibre exposes

```text
1 + 2 + ... + 8 = 36
```

proposal units while the final carrier contains only eight proposals.  This is
an execution-cost witness, not permission to replace the reducer with an
incremental fold.

The companion Agda surfaces are:

- `ConsumerSufficientComplexityExact.agda`: consumer observation, residual,
  provenance and non-increasing operational-description requirements;
- `OwnerFibreReductionComplexityExact.agda`: repeated full-fibre exposure,
  independent-owner commutation, and the stronger append-homomorphism required
  before same-owner incremental reduction;
- `SignatureBucketReductionFactorizationExact.agda`: the proof boundary for an
  internal cache over the reducer's exact semantic signature buckets.

## Complexity findings from the current Python/PostgreSQL pass

### Parentless sentence ancestor maintenance

Sentence interfaces are closed before paragraph/adaptive/document parent
interfaces exist.  The former `rebuild_pnf_interface_ancestors()` implementation
deleted two ancestor projections before discovering `parent_interface_id IS
NULL`.  Migration 141 moves the parent lookup ahead of those writes.  A
parentless sentence interface now performs no ancestor-table mutation; parented
interfaces retain the previous construction.

### Document ancestor materialization

The former document rebuild first deleted the whole document ancestor projection
and then looped over every interface, invoking the per-interface builder.  That
repeated per-interface deletes against already-cleared tables and materialized
binary lifting one interface at a time.

Migration 142 makes the relation explicit as one recursive projection

```text
(descendant interface, ancestor interface, distance).
```

Binary-lifting rows are the subset whose distance is `2^p`; typed ancestors are
the nearest ancestor for each region kind.  Both are inserted set-wise.  The
semantic parent relation and return-count contract are unchanged.

### Owner reduction

The bounded streaming owner may repeatedly invoke the canonical reducer over the
entire accumulated coarse owner fibre.  This can create triangular physical scan
exposure across many proposal waves.  The canonical reducer itself first
partitions by

```text
(semantic coordinate, fibre kind, factor type, structural signature)
```

and performs compatibility grouping only inside each signature bucket.

However, proposal validity also depends on the global `known_dependency_refs`
set.  A correct cache must therefore separate

```text
dependency-validity invalidation
    -> signature-local compatibility reduction.
```

Changing the public `OwnerKey` or incrementally folding same-owner summaries is
not licensed merely by the cost profile.  The concrete reducer uses canonical
proposal ordering and greedy first-compatible grouping; same-owner incremental
execution requires the stronger homomorphism proof formalized in Agda.

### Global lookup refresh

`refresh_pnf_visible_lookup()` is currently an alias for the global lookup
refresh.  The hierarchy phase must perform an initial global publication because
that refresh drives demand planning before adjacent reconciliation.  Paragraph
adjacency then creates/updates pair-interface lookup rows, so the later final
refresh also has semantic work to publish.  The safe optimization is therefore
a changed-interface/delta refresh for the second boundary, not deletion of one
of the two semantic phases.  That optimization remains gated on an explicit
changed-interface certificate.

## Empirical boundary

These structural changes are designed to remove repeated work before another
large ingest, but they are not themselves wall-time measurements.  The durable
complete-tranche phase timer remains the empirical authority for deciding which
minutes/hours phase dominates after the migrations are applied.
