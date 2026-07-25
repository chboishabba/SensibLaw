# PostgreSQL single semantic spine

## Normative repository policy

SensibLaw has one active semantic persistence and query authority: PostgreSQL.

```text
source admission
-> canonical compiler
-> PNF lifecycle
-> Domain IR
-> generic derived follow projection
-> PostgreSQL persistence
-> PostgreSQL query
-> detached presentation response
```

Having a PostgreSQL schema is not enough. An active workflow complies only when
its semantic reads and writes traverse the PostgreSQL spine.

## SQLite status

SQLite is deprecated as a runtime and remains only as a bounded historical
reference/import fixture.

Permitted:

```text
historical SQLite fixture
-> explicit legacy importer
-> validated PostgreSQL rows
-> normal PostgreSQL runtime
```

Prohibited:

```text
CLI or workflow
-> SQLite read model
-> semantic decision, follow graph, world model, or handoff
```

There is no automatic PostgreSQL-to-SQLite fallback and no dual semantic
authority. The legacy importer must emit a receipt containing the source hash,
imported/rejected counts, resulting PostgreSQL revision refs, and discrepancies.
After import, SQLite is closed and never queried by the runtime.

The large `fact_intake.read_model` module is retained temporarily as the legacy
reference implementation and fixture compatibility source. New runtime code must
use `src.fact_intake.postgres_runtime` or `src.policy.postgres_semantic_spine`.
Feature completeness is migrated into the one spine; it is not preserved by
operating parallel implementations.

## Follow projections

Migration `024_generic_follow_projection.sql` defines one generic relational,
derived-only follow model:

- `pnf_follow_projection`
- `pnf_follow_node`
- `pnf_follow_edge`
- edge evidence, provenance, and admissibility-ground relations
- legal and non-legal derived views

AU and GWB profiles may select relation families and presentation labels. They
must not construct separate semantic edges, maintain lane-owned node identity,
decide admissibility, or deserialize a previous graph bundle.

Every follow row is:

- derived-only;
- challengeable;
- unable to promote truth;
- unable to execute a rule;
- closed over durable canonical parent references before persistence.

Deleting an AU/GWB compatibility wrapper must lose no canonical semantic
information.

## JSON boundary

JSON is an outer presentation/transport format only.

A CLI or API may query relational rows and serialize a detached response. That
response:

- is not semantic input;
- is not persisted as the sole representation of a semantic relation;
- does not determine identity, admissibility, closure, or cache keys;
- is never deserialized to rebuild compiler or follow state.

Putting a former nested graph wholesale into JSONB does not satisfy this policy.
Semantic relations requiring identity, joins, revision lineage, or foreign keys
must remain relational.

## Reference binding

The primary compiler must establish:

```text
parser observation
-> pronominal argument factor
-> reference alternatives
-> deterministic binding candidate set
```

Projection is corpus-neutral and uses POS, morphology, dependency, span,
relation, and source-factor provenance. No GWB vocabulary or pronoun catalogue is
permitted. The compiler contract is incremented so pre-reference cached artefacts
cannot masquerade as reference-capable.

## Lifecycle precedence

Definitive invalidation is constitutive:

```text
NO_TYPED_MEET -> violated -> rejected
```

Candidate-producing support does not convert a definitive invalidation into
`both`. `both` remains reserved for genuine derivational support plus
counter-support.

Projection demands bind a durable graph factor. Fibre-summary, resolution, and
plural-alternative identities remain provenance and are not substituted as
foreign-key parents. The compiler rejects non-durable demand bindings before
PostgreSQL persistence.

## Zelph handoff

Engine transport success is not output-contract success. Callers must consume an
explicit receipt with one of:

- `engine_unavailable`
- `engine_failed`
- `blocked_input`
- `executed_no_match`
- `executed_with_output`
- `failed_required_output`

A profile declares required output predicates. AU handoff succeeds only when
`au_procedural_fact` was emitted. A compatibility `ok` field, where retained, is
derived and deprecated.

## Performance evidence

Semantic timing and presentation serialization are reported separately. Corpus
claims require p50, p90, and maximum values over the admitted corpus, together
with row/document sizes, admission manifests, phase ledgers, semantic identity
comparisons, projection-demand counts, Legal IR projected/blocked outcomes, and
zero-external-network receipts.

The minimum timed stages are:

- document compilation;
- base reduction;
- semantic lifecycle;
- follow construction;
- follow persistence;
- follow query;
- Domain IR projection;
- total PostgreSQL transaction.

Synthetic single-document timings are smoke evidence, not corpus performance
claims.
