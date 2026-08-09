# Sparse Fibred PNF Frontiers

## Status

Implemented by PostgreSQL migrations:

- `062_sparse_fibred_pnf_frontiers.sql`
- `063_sparse_actor_profile_null_normalisation.sql`

The implementation replaces document-wide reconsideration of closed region
interiors with hierarchical reconciliation over sparse typed frontiers.

## Compiler invariant

For every closed region `r`, later stages may observe only:

- an admitted outward export;
- a compressed actor/action profile;
- an unresolved typed demand; or
- immutable provenance addressed through one of those boundary objects.

Equivalently:

```text
x not in frontier(r)
=> x cannot be reconsidered outside r
```

The child proposition graph remains authoritative provenance, but it is not
copied into every parent interface and it is not searched globally.

## Example: resolving “you”

A paragraph may close all of its local propositions while retaining one
abstract actor variable:

```text
local graph:
  notify(alpha, beta)
  must_respond(beta)

surface evidence:
  beta was realised by “you”

outward demand:
  target kind: actor
  discourse role: addressee
  factor participation: recipient of notify
  local action constraint: must respond
  recency/scope: surrounding paragraph or parent region
```

The parent does not reopen the paragraph or scan every document object. It
compares this typed hole with compressed actor profiles exported by its direct
children:

```text
actor B:
  roles: applicant, notice recipient
  actions: submitted application, may respond
```

A unique compatible witness is bound. Several compatible witnesses remain an
explicit ambiguous frontier result. No local witness rises to the next parent;
at the document root, no witness becomes `deferred_world`.

## Boundary representations

### Interface exports

`semantic_pnf_interface_export` now records:

- `scope_class`
- `origin_interface_id`
- `outward_required`

Definitions, scopes, explicit bindings, temporal/modal declarations,
recurrent identities, salient actors and unresolved demands can cross a
boundary. Ordinary child propositions do not.

### Typed demands

`semantic_pnf_demand_constraint` normalises each demand into numeric keys for:

- expected factor type;
- expected object kind;
- lexical symbol;
- semantic role; and
- residual type.

A demand is therefore a constrained hole, not a request for unrestricted
search.

### Actor/action fibres

`semantic_pnf_actor_profile` stores the minimum relational summary needed to
answer outward actor demands:

- actor identity and kind;
- role in a factor;
- factor type and predicate;
- occurrence count;
- first and last structural coordinates; and
- promotion score.

Numeric zero is the canonical unspecified profile dimension. Semantic symbol
identities remain positive.

### Resolution outcomes

`semantic_pnf_frontier_resolution` records one of:

- `no_witness`
- `resolved_unique`
- `ambiguous`
- `generic`
- `plural`
- `inapplicable`
- `deferred_world`

The first executable resolver currently produces `resolved_unique`,
`ambiguous`, `no_witness`, and `deferred_world`. The other states are explicit
schema commitments for later generic, plural and quotation-role rules; they
are not falsely inferred by the initial implementation.

## Closure algorithm

When a non-sentence region closes:

1. Read only its direct child interfaces.
2. Aggregate already-compressed child actor profiles.
3. Add direct factor participation to those profiles.
4. Remove low-salience one-off actor summaries unless an exported typed demand
   can ask for them.
5. Carry unresolved demands upward.
6. Carry explicit definitions/scopes/bindings upward.
7. Admit only salient, recurrent, demanded or already-resolved actors.
8. Admit full factors only when they are strongly supported or explicitly
   demanded.
9. Rebuild the parent lookup from admitted exports only.
10. Resolve exported demands against the compressed parent frontier.
11. Bind a demand only when exactly one witness survives.
12. Remove resolved demands from the outward frontier.
13. Update interface measures and write a reduction receipt.

This occurs in one set-oriented function,
`rebuild_numeric_pnf_parent_frontier(interface_id)`, after the parent region
moves to a closed state.

## Explicit stages

Demand planning is no longer launched by an `AFTER INSERT` trigger on a broad
global lookup table. The old hidden triggers are dropped.

The explicit final path is:

```text
close child fibres
-> reduce parent frontiers bottom-up
-> project the closed document frontier
-> refresh the root-only global lookup
-> publish receipts
```

`refresh_pnf_visible_lookup` remains as a compatibility call surface, but now
performs this explicit sparse reduction and root projection. It no longer
materialises ancestor exports into every descendant interface.

## Root-only lookup

`refresh_pnf_global_lookup_ids` now indexes only the closed document interface.
It incrementally deletes stale root rows and upserts admitted root lookup rows.
Closed sentence, paragraph and adaptive-block interiors remain in their local
interfaces and provenance tables.

The final cost target is therefore related to:

```text
root frontier size
+ unresolved demand count * indexed compatible actor profiles
```

not:

```text
all regions * all extracted objects
```

## Observability

Each parent reduction records:

- child interface count;
- input export count;
- output export count;
- compressed actor-profile count;
- unresolved demand count;
- uniquely resolved demand count; and
- elapsed milliseconds.

Document stages record their row counts and elapsed milliseconds separately:

- `sparse_frontier_reduction`
- `root_global_lookup_refresh`
- `root_visible_projection`

Run:

```bash
.venv/bin/python scripts/report_numeric_pnf_frontier.py \
  --database-url postgresql://postgres@127.0.0.1:5433/sensiblaw_tranche \
  --run-ref RUN_REF \
  --document-ref DOCUMENT_REF
```

The report shows per-interface compression and root lookup cardinality. A
healthy hierarchy should show a strong reduction from the sum of child exports
to each parent frontier. A root frontier close to the full document object
inventory is a failed reduction, even if the SQL finishes quickly.

## Rollout

Apply migrations through `063` before restarting the tranche process. Existing
long-running Python/PostgreSQL transactions do not hot-reload schema or
function definitions reliably enough for a controlled comparison.

Use a fresh database or a copied benchmark database for the first acceptance
run. Keep the old run as a forensic baseline.

Recommended acceptance sequence:

```text
1. apply migrations 062 and 063
2. run migration/static tests
3. compile one medium document
4. inspect frontier receipts and root cardinality
5. verify unique/ambiguous/deferred demand outcomes
6. compile document 0007 as the performance baseline
7. compile documents 0008-0010 only after semantic checks pass
```

## Acceptance criteria

Correctness:

- no resolved demand lacks an explicit target;
- a unique witness binds deterministically;
- multiple witnesses remain ambiguous;
- a root no-witness becomes deferred-world;
- resolved demands disappear from outward interfaces;
- every lookup row has a corresponding admitted export;
- child provenance remains intact;
- no JSON/JSONB execution authority is introduced.

Performance and reduction:

- no hidden demand-planning trigger runs during lookup insertion;
- no recursive visible-ancestor materialisation occurs;
- global lookup rows equal the admitted root projection, not all closed
  interface rows;
- each nontrivial parent has a recorded input/output frontier ratio;
- document closure time is attributed separately from lookup projection;
- large documents do not require increasing an interface budget merely because
  local interiors were copied to the root.

## Remaining extensions

The initial resolver intentionally binds only a unique concrete object or
factor witness. Later rules can add evidence-backed handling for:

- generic legal classes;
- plural addressees;
- quotation/example inapplicability;
- cross-document/world identity; and
- weighted ambiguity preservation.

Those extensions should operate over the same typed sparse frontiers rather
than restoring document-wide candidate scans.
