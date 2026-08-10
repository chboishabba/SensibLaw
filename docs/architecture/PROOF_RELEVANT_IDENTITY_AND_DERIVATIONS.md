# Proof-Relevant Identity Fibres and Factor Derivations

## Status

Implemented by PostgreSQL migrations:

- `069_proof_relevant_identity_fibres.sql`
- `070_proof_relevant_factor_derivations.sql`
- `071_sparse_root_derivation_publication.sql`
- `072_retractable_identity_and_external_alignment.sql`

and the generic reporting surface:

- `src/storage/postgres/epistemic_factor_report.py`
- `scripts/generate_entity_factor_report.py`

The design extends sparse fibred PNF closure without destructively merging local
objects or factors.

## Epistemic stack

The runtime distinguishes:

```text
Level 0  source observation / local surface identity
Level 1  immutable role-labelled factor hyperedge
Level 2  admitted identity derivation witness
Level 3  proposition obtained by witnessed identity substitution
Level 4  interpretation, which is outside structural authority unless separately derived
```

The central entity-neighbourhood query is proof-relevant:

```text
G_E = union { Neighbourhood(o) | there exists pi : o ==> E }
```

A local object's spelling is not itself a proof that the object denotes one
world-unique entity. Paragraph membership, proximity, n-grams and co-occurrence
are never identity witnesses.

## Canonical entity bases are not destructive merges

`semantic_pnf_canonical_entity` is a base over which local object occurrences can
be fibred. Local `semantic_pnf_object` rows remain immutable textual evidence.
The entity layer therefore does not rewrite:

```text
Reagan
Ronald Reagan
the President
he
```

into one object. Instead each admitted path retains its own witness.

Authority is explicit:

```text
surface_local       world_canonical = false
document_derived    world_canonical = false
corpus_derived      world_canonical = false
external_authority  world_canonical = true
```

Thus a literal surface `Reagan` does not by itself prove the external-world
identity `Ronald Wilson Reagan`. World identity requires an explicit external
authority namespace and identifier.

## Identity witnesses

`semantic_pnf_identity_witness` records immutable evidence including:

```text
source object
target canonical entity
witness kind
authority class
source interface
demand id / resolution interface when applicable
candidate count
```

Witness kinds include:

```text
resolution anchor
apposition
proper-name expansion
title/role closure
anaphor demand resolution
explicit alias
definition equivalence
typed-demand unique resolution
corpus identity closure
external authority alignment
```

Admission is separate in `semantic_pnf_identity_witness_admission`. Rejecting or
superseding a witness therefore does not delete the immutable witness evidence.

### Typed proof constraints

For demand-derived witnesses,
`semantic_pnf_identity_witness_constraint` copies the exact typed demand
constraints that survived unique resolution. This makes the identity
substitution itself auditable rather than merely recording its result.

### Ambiguity invariant

`semantic_pnf_identity_projection` emits a projection only when accepted
witnesses at an authority class agree on exactly one entity:

```text
count(distinct target_entity_id) = 1
```

Competing accepted targets produce no projection. Ambiguity remains explicit.

## From frontier resolution to identity proof

`refresh_numeric_pnf_identity_witnesses(run_id, document_id)` materialises
identity only from `resolved_unique` frontier results whose target is an object.
A demand-derived source object is projected only when:

```text
outcome = resolved_unique
candidate_count = 1
source_object_id is explicit
selected target is an object
```

`refresh_numeric_pnf_demand_source_objects` backfills a source object only when
exactly one object in the demand's own source region matches the recorded surface
or canonical lexical symbol. It never searches a paragraph for a nearby person.

This converts the former methodological rule into a database invariant:

```text
same paragraph as Reagan != identity with Reagan
```

## Retractable current identity

Migration 072 makes current document-derived identity admission recomputable.
Before a document's identity frontier is refreshed, its previously accepted
`document_derived` witnesses are marked `superseded`. The current set of uniquely
justified witnesses is then re-admitted.

The immutable witness rows remain available as proof provenance; only the current
admission state changes.

Level-3 `identity-substitution:v1` derivations are also rebuilt from the current
identity projection. Therefore a pronoun resolution that ceases to have an
accepted proof cannot leave a stale substituted proposition in the current
semantic surface.

This is current-state retractability rather than destructive rewriting:

```text
local object/factor evidence     retained
identity witness evidence        retained
current witness admission        recomputed
current Level-3 substitutions    rebuilt
```

## Explicit external-world alignment

World identity is admitted only through an explicit authority operation:

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

The function performs no name search, similarity search, paragraph search or
co-occurrence lookup. The caller supplies the external authority namespace and
identifier explicitly. The resulting canonical entity has authority class
`external_authority` and the local-to-world projection is stored as witness kind
`external_authority_alignment`.

Examples of authority namespaces may include Wikidata, a legal authority
registry, or another explicitly governed identity namespace. The database does
not equate those namespaces merely because labels happen to match.

## Witnessed factor substitution

Original PNF factors remain Level-1 evidence. Identity substitution creates a
separate `semantic_pnf_factor_derivation` with:

```text
rule
premise factor
scope interface
authority class
preserved predicate
preserved modal state
preserved temporal state
role-labelled derived arguments
identity witness ids for every substituted argument
```

An argument promoted to a canonical entity must carry a non-empty witness-id
array. The corresponding original local object remains in `source_object_id`.

The derived proposition therefore has the form:

```text
F(surface bearer = he)
pi : he ==> document-entity:E
-------------------------------- identity-substitution:v1
F(entity bearer = E)
```

without mutating `F`.

## Factor composition

A shared argument between two factors is not sufficient to assert a new semantic
proposition. Migration 070 therefore introduces only bounded
`semantic_pnf_factor_composition_candidate` rows.

A bridge is admissible as a candidate when either:

1. both factors share the exact same immutable local object in the same local
   factor region; or
2. distinct local objects project to the same canonical entity at the same
   explicit identity authority class.

Candidates are bounded per bridge. The installed rule is deliberately named:

```text
shared-argument-composition:candidate-v1
```

and explicitly licenses no conclusion. A future domain rule must inspect roles,
predicates, modality, scope, qualifiers and defeaters before creating an admitted
factor-composition derivation.

This separates:

```text
structural composability
```

from:

```text
semantic entailment
```

which prevents adjacency or shared participants from silently becoming claims.

## Monotone growth and retraction

For monotone evidence additions, an entity's witnessed neighbourhood can expand
without rewriting prior Level-1 facts:

```text
G_E^0 subset G_E^1 subset G_E^2 ...
```

When evidence is withdrawn or becomes ambiguous, current witness admission can
retract a fibre. The immutable local factors and witness evidence remain intact,
while current Level-3 projections are rebuilt. Thus monotonicity is a property of
pure evidence addition, not an excuse to preserve a claim after its proof is no
longer admitted.

## Sparse publication boundary

The benchmark performance migration `062_demand_planner_performance.sql` was
added after some databases had already applied the sparse-frontier migration and
redefined `refresh_pnf_global_lookup_ids` over all closed interfaces. Migration
071 is intentionally later and restores the canonical contract:

```text
global lookup = closed document-root frontier only
```

It also converges `plan_numeric_pnf_demand_candidates_ids` on the sparse
bottom-up reducer, so fresh databases and upgraded benchmark databases cannot end
with different semantic planner definitions merely because the two 062 files
were encountered in a different historical sequence.

Migration 071 inserts a `proof_relevant_derivations` stage between bottom-up
frontier reduction and root publication.

The final explicit path is:

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

Use:

```bash
uv run python scripts/generate_entity_factor_report.py \
  --database-url "$DATABASE_URL" \
  --surface reagan \
  --surface ronald \
  --output .tmp/reagan-proof-report.md
```

The repeated `--surface` arguments choose entry-point lexical surfaces only;
they are not an assertion that those surfaces share a world identity.

To materialise derivations for one already-known numeric run/document before
reading:

```bash
uv run python scripts/generate_entity_factor_report.py \
  --database-url "$DATABASE_URL" \
  --surface reagan \
  --refresh-run-id 7 \
  --refresh-document-id 11
```

The report separately shows:

- direct Level-1 factors;
- admitted identity entities and their authority class;
- proof objects and typed constraint counts;
- Level-3 witnessed substitutions;
- structural factor-composition candidates; and
- whether any world-canonical identity has actually been proven.

The legacy Reagan report script is now only a thin fixture over this generic
reporter and contains no Reagan-specific resolution logic.

## Acceptance invariants

Correctness:

- paragraph co-presence never creates identity;
- candidate multiplicity greater than one never creates identity;
- a demand-derived identity witness requires a uniquely selected target;
- competing accepted entity targets produce no identity projection;
- world-canonical identity requires explicit external authority evidence;
- document-derived witness admission is recomputed and retractable;
- current identity substitutions are rebuilt after witness retraction;
- identity substitution never mutates its premise factor;
- every substituted argument retains non-empty identity witness ids;
- shared-argument composition produces candidates only;
- composition across distinct local objects requires the same admitted entity
  and the same explicit authority class;
- global lookup and planner semantics remain sparse after all later migrations;
- fresh and incrementally upgraded databases converge on the same final planner
  and publication contract.

Epistemic reporting:

- direct surface identity and world identity are displayed separately;
- no co-occurrence query is part of the generic report path;
- composition candidates are never worded as established propositions;
- interpretation beyond graph semantics is explicitly marked outside structural
  authority.
