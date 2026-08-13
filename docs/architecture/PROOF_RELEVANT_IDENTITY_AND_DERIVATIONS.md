# Proof-Relevant Identity Fibres and Factor Derivations

## Status

Implemented by PostgreSQL migrations:

- `069_proof_relevant_identity_fibres.sql`
- `070_proof_relevant_factor_derivations.sql`
- `071_sparse_root_derivation_publication.sql`
- `072_retractable_identity_and_external_alignment.sql`
- `073_external_identity_ref_and_retraction.sql`
- `074_identity_admission_integrity.sql`

Generic reporting is implemented by:

- `src/storage/postgres/epistemic_factor_report.py`
- `scripts/generate_entity_factor_report.py`

The design extends sparse fibred PNF closure without destructively merging local
objects or factors.

## Epistemic stack

```text
Level 0  source observation / local surface identity
Level 1  immutable role-labelled factor hyperedge
Level 2  admitted identity derivation witness
Level 3  proposition obtained by witnessed identity substitution
Level 4  interpretation, outside structural authority unless separately derived
```

The entity neighbourhood is proof-relevant:

```text
G_E = union { Neighbourhood(o) | there exists pi : o ==> E }
```

A local object's spelling is not itself a proof that the object denotes one
world-unique entity. Paragraph membership, proximity, n-grams and co-occurrence
are never identity witnesses.

## Canonical entity bases, not destructive merges

`semantic_pnf_canonical_entity` is a base over which immutable local
`semantic_pnf_object` occurrences can be fibred. The runtime does not rewrite:

```text
Reagan
Ronald Reagan
the President
he
```

into one graph object. Each admitted path retains its own proof.

Identity authority is explicit:

```text
surface_local       world_canonical = false
document_derived    world_canonical = false
corpus_derived      world_canonical = false
external_authority  world_canonical = true
```

Thus a literal surface `Reagan` does not prove the external-world identity
Ronald Wilson Reagan. World identity requires an explicit authority namespace
and identifier.

## Identity witnesses

`semantic_pnf_identity_witness` records immutable evidence:

```text
source object
target canonical entity
witness kind
authority class
source interface
demand/resolution ids where applicable
candidate count
```

Witness kinds include resolution anchors, apposition, proper-name expansion,
title/role closure, anaphor demand resolution, explicit aliases, definition
equivalence, uniquely resolved typed demands, corpus closure and external
authority alignment.

Current authority is separate in
`semantic_pnf_identity_witness_admission`. Rejecting or superseding a witness
does not delete its historical proof record.

For demand-derived witnesses,
`semantic_pnf_identity_witness_constraint` preserves the typed constraint
conjunction that justified the unique resolution.

## Unique projection and admission integrity

The current projection is deliberately fail-closed. An identity can participate
in `semantic_pnf_identity_projection` only when:

```text
admission_state = accepted
candidate_count = 1
witness.authority_class = target_entity.authority_class
count(distinct target_entity_id) = 1 for that source/authority fibre
```

Migration 074 enforces the first three conditions at the write boundary with
`semantic_pnf_identity_admission_integrity`; a future writer cannot mark a
multi-candidate witness accepted or attach a document-authority witness to an
external-authority entity.

The projection view repeats these checks defensively. During upgrade, migration
074 marks any historically invalid accepted admission `superseded`, removes
Level-3 substitutions no longer backed by a current projection, and discards
identity-bridge composition candidates so they are rebuilt from the stricter
frontier.

This makes `accepted` itself semantically meaningful rather than treating an
invalid accepted row as harmless merely because a downstream view hides it.

## From frontier resolution to identity proof

`refresh_numeric_pnf_identity_witnesses(run_id, document_id)` materialises
identity only from `resolved_unique` object-target frontier resolutions.
Demand-derived source projection requires:

```text
outcome = resolved_unique
candidate_count = 1
source_object_id is explicit
selected target is an object
```

`refresh_numeric_pnf_demand_source_objects` can backfill a source object only
when exactly one object in the demand's **own source region** matches the
recorded surface/canonical lexical symbol. It never searches a paragraph for a
nearby actor.

Hence:

```text
same paragraph as Reagan != identity with Reagan
```

is a runtime invariant rather than a reporting convention.

## Retractable current identity

Migration 072 makes document-derived identity admission recomputable. Before a
document identity frontier is refreshed, previously accepted
`document_derived` witnesses are superseded and exactly the currently uniquely
justified witnesses are re-admitted.

Level-3 identity substitutions are rebuilt from the current identity projection,
so a pronoun resolution that ceases to have proof cannot leave a stale current
proposition.

Migration 073 adds explicit witness retraction:

```sql
SELECT execution.retract_numeric_pnf_identity_witness(witness_id);
```

Retraction retains the immutable witness but marks its current admission rejected
and rebuilds the affected document's Level-3 substitutions and bounded
factor-composition frontier in the same transaction.

```text
local object/factor evidence     retained
identity witness evidence        retained
current witness admission        recomputed/retractable
current Level-3 substitutions    rebuilt immediately
composition frontier             rebuilt immediately
```

## Explicit external-world alignment

World identity is admitted only through:

```sql
SELECT *
FROM execution.admit_numeric_pnf_external_identity_alignment(
    source_object_id,
    authority_namespace,
    authority_identifier,
    canonical_symbol_id,
    source_interface_id
);
```

This operation performs no label discovery, fuzzy matching, paragraph search or
co-occurrence lookup. The caller supplies the authority namespace and identifier.
The result has authority class `external_authority` and witness kind
`external_authority_alignment`.

Migration 073 derives the external entity ref from:

```text
UTF8(namespace) || 0x00 || UTF8(identifier)
```

before SHA-256 hashing. PostgreSQL text cannot contain NUL, so the namespace /
identifier boundary is unambiguous.

External admission and retraction both rebuild the affected current Level-3 and
composition surfaces immediately.

## Witnessed factor substitution

Original PNF factors remain Level-1 evidence. Identity substitution creates a
separate `semantic_pnf_factor_derivation` containing:

```text
rule
premise factor
scope interface
authority class
preserved predicate/modal/temporal state
role-labelled derived arguments
identity witness ids for every substituted argument
```

Every identity-substituted argument retains its source object and must carry a
non-empty witness-id array:

```text
F(surface bearer = he)
pi : he ==> document-entity:E
-------------------------------- identity-substitution:v1
F(entity bearer = E)
```

The premise `F` is never mutated.

## Factor composition is not entailment

A shared argument between two factors creates only a bounded
`semantic_pnf_factor_composition_candidate`.

A structural bridge is allowed when either:

1. the factors share the exact same immutable local object in the same local
   factor region; or
2. distinct local objects project to the same canonical entity at the same
   explicit identity authority class.

The installed rule is deliberately named:

```text
shared-argument-composition:candidate-v1
```

and licenses no conclusion. A later domain rule must inspect roles, predicates,
modality, scope, qualifiers and defeaters before admitting a composition
proposition.

Thus:

```text
structural composability != semantic entailment
```

## Monotone growth and retraction

For pure evidence additions:

```text
G_E^0 subset G_E^1 subset G_E^2 ...
```

without rewriting Level-1 facts. When evidence is withdrawn or becomes
ambiguous, the current fibre can retract while immutable factors and witness
evidence remain available for audit.

## Sparse publication boundary

The benchmark migration `062_demand_planner_performance.sql` had redefined the
global lookup over all closed interfaces on some upgraded databases. Migration
071 deliberately restores and converges the canonical contract:

```text
global lookup = closed document-root frontier only
plan_numeric_pnf_demand_candidates_ids = bottom-up sparse reduction
```

so fresh and incrementally upgraded databases end with the same semantic planner
regardless of the historical ordering of the two `062_*` files.

The final path is:

```text
local parser observations
-> local PNF factors
-> sparse frontier reduction
-> resolved typed holes
-> proof-relevant identity witnesses
-> identity-substitution derivations
-> bounded factor-composition candidates
-> root-only visible/global publication
```

No derivation stage reopens closed child interiors globally.

## Generic reporting

```bash
uv run python scripts/generate_entity_factor_report.py \
  --database-url "$DATABASE_URL" \
  --surface reagan \
  --surface ronald \
  --output .tmp/reagan-proof-report.md
```

Repeated `--surface` arguments select lexical entry points only; they do not
assert that those surfaces share a world identity.

The report separately exposes:

- direct Level-1 factors;
- admitted entity bases and authority classes;
- identity proof objects and typed constraint counts;
- Level-3 witnessed substitutions;
- structural factor-composition candidates; and
- whether world-canonical identity is actually proven.

The legacy Reagan script is now only a thin fixture over this generic reporter;
it contains no Reagan-specific resolution logic.

## Acceptance invariants

- paragraph co-presence and lexical proximity never create identity;
- candidate multiplicity greater than one cannot be accepted as identity;
- witness authority must equal target-entity authority;
- competing accepted targets produce no identity projection;
- world-canonical identity requires explicit external authority evidence;
- external entity refs have an unambiguous namespace/identifier byte boundary;
- admission/retraction immediately refresh current derived surfaces;
- identity substitution never mutates its premise factor;
- every substituted argument retains non-empty witness ids;
- shared-argument composition produces candidates only;
- distinct-object composition requires the same entity and authority class;
- global lookup and planner semantics remain sparse after all later migrations;
- no JSON/JSONB execution authority is introduced;
- direct surface identity and world identity remain distinct in reports;
- interpretation beyond graph semantics is outside structural authority unless
  separately derived.
