# Sparse Fibred PNF Frontiers

## Status

Implemented by PostgreSQL migrations:

- `062_sparse_fibred_pnf_frontiers.sql`
- `063_sparse_actor_profile_null_normalisation.sql`
- `064_anaphor_surface_lexical_evidence.sql`
- `065_actor_profile_dimension_integrity.sql`
- `066_standalone_actor_profiles.sql`
- `067_typed_frontier_candidate_constraints.sql`

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

The surface word “you” is retained in `surface_lexical_symbol_id`. It is not
used as an exact identity key for the actor witness. This prevents the solver
from requiring the eventual actor’s canonical lexical symbol to literally be
“you”.

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
- canonical lexical identity, when applicable;
- semantic role;
- residual type;
- definition keys; and
- explicit scope keys.

Constraints carry required/optional status and positive/negative polarity.
Positive required constraints are conjunctive: every one must be witnessed by
the same candidate actor or factor, although different actor/action profile
rows may jointly provide the evidence. A negative required constraint excludes
a candidate when the forbidden evidence is present.

For anaphoric demands, the pronoun surface is retained separately and the
canonical lexical identity constraint is absent. A demand is therefore a
constrained hole, not a request for unrestricted search.

### Actor/action fibres

`semantic_pnf_actor_profile` stores the minimum relational summary needed to
answer outward actor demands:

- actor identity and kind;
- role in a factor;
- factor type and predicate;
- occurrence count;
- first and last structural coordinates; and
- promotion score.

Object exports also create a generic actor summary with zero role, factor and
predicate dimensions in one statement-level operation. Factor participation
enriches that actor with relational summaries. This permits a bare named actor
to answer a kind/identity demand without pretending that it performed an
unobserved action.

Numeric zero is the canonical unspecified profile dimension. Concrete nonzero
dimensions have generated nullable foreign-key projections into
`semantic_symbol`; zero remains absence without requiring hot-path trigger
queries. All four profile dimensions are non-null and nonnegative.

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
4. Retain generic standalone-actor profiles for admitted object exports.
5. Remove low-salience one-off actor summaries unless an exported typed demand
   can ask for them.
6. Carry unresolved demands upward.
7. Carry explicit definitions/scopes/bindings upward.
8. Admit only salient, recurrent, demanded or already-resolved actors.
9. Admit full factors only when they are strongly supported or explicitly
   demanded.
10. Rebuild the parent lookup from admitted exports only.
11. Generate a bounded candidate set against the compressed parent frontier.
12. Apply all required positive and negative typed constraints set-wise to the
    newly inserted candidates.
13. Bind a demand only when exactly one witness survives.
14. Remove resolved demands from the outward frontier.
15. Update interface measures and write a reduction receipt.

The parent reduction occurs in
`rebuild_numeric_pnf_parent_frontier(interface_id)` after the parent region
moves to a closed state. Constraint filtering is an `AFTER INSERT ... FOR EACH
STATEMENT` operation over the newly inserted bounded candidate relation; it
does not scan global document objects.

## Explicit stages

Demand planning is no longer launched by an `AFTER INSERT` trigger on a broad
global lookup table. The old hidden triggers are dropped.

The explicit final path is:

```text
close child fibres
-> reduce parent frontiers bottom-up
-> filter bounded candidates by typed constraints
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
+ bounded candidate count * typed constraint count
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

Apply migrations through `067` before restarting the tranche process. Existing
long-running Python/PostgreSQL transactions do not hot-reload schema or
function definitions reliably enough for a controlled comparison.

Use a fresh database or a copied benchmark database for the first acceptance
run. Keep the old run as a forensic baseline.

Recommended acceptance sequence:

```text
1. apply migrations 062 through 067
2. run static, catalog and PostgreSQL semantic fixture tests
3. compile one medium document
4. inspect frontier receipts and root cardinality
5. verify unique/ambiguous/deferred demand outcomes
6. verify multi-action conjunction and negative constraints
7. compile document 0007 as the performance baseline
8. compile documents 0008-0010 only after semantic checks pass
```

## Acceptance criteria

Correctness:

- no resolved demand lacks an explicit target;
- anaphor surface evidence is preserved without becoming actor identity;
- a unique witness binds deterministically;
- multiple witnesses remain ambiguous;
- a root no-witness becomes deferred-world;
- all required positive constraints are witnessed;
- any matched negative required constraint excludes the candidate;
- resolved demands disappear from outward interfaces;
- every lookup row has a corresponding admitted export;
- child provenance remains intact;
- concrete actor-profile dimensions retain referential integrity;
- no JSON/JSONB execution authority is introduced.

Performance and reduction:

- no hidden demand-planning trigger runs during lookup insertion;
- no recursive visible-ancestor materialisation occurs;
- global lookup rows equal the admitted root projection, not all closed
  interface rows;
- each nontrivial parent has a recorded input/output frontier ratio;
- document closure time is attributed separately from lookup projection;
- actor-profile integrity introduces no per-row catalog query trigger;
- standalone actor capture is statement-level;
- typed constraint filtering is statement-level and runs only over bounded
  candidate insertions;
- large documents do not require increasing an interface budget merely because
  local interiors were copied to the root.

## Focused semantic fixtures

`test_sparse_fibred_frontier_resolution.py` constructs a minimal PostgreSQL
hierarchy and verifies:

1. the surface “you” is retained while exact lexical identity is cleared;
2. one compatible actor resolves the demand and removes it from the root
   frontier;
3. two compatible actors preserve ambiguity and do not set a target;
4. no compatible actor becomes `deferred_world` at the root; and
5. global lookup contains no non-root interface rows.

`test_typed_frontier_candidate_constraints.py` verifies that:

1. a batch of bounded actor candidates is filtered by object kind, role,
   factor-type and predicate constraints;
2. evidence may be supplied by compressed actor/action profiles;
3. a candidate missing one required constraint is removed; and
4. a matched negative constraint removes an otherwise compatible candidate.

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
