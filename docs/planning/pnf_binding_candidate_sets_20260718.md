# Set-valued PNF binding candidates

Date: 2026-07-18
Status: implemented PostgreSQL operational tranche
Compiler contract: `postgres-semantic-compiler:v0_7`

## Purpose

The v0.6 compatibility compiler preserved document-local antecedent ambiguity by
expanding every:

```text
reference × referential type × candidate
```

into complete evidence and often complete factor alternatives. That remains
available only for explicit legacy JSON/review export. It is not executed by the
PostgreSQL operational compiler.

The operational construction is:

```text
parser-observed PNF argument
× structural accessibility declaration
× referential type
× PNF-kind/morphology compatibility declaration
→ BindingCandidateSet
× normalized members
× compatibility assessments
× compact exclusion summaries
→ immutable factor revision delta
→ revision-linked demands
```

Candidate membership is not identity closure. An empty set is not evidence that
a grammatical argument is expletive.

## PNF reference projection

Every parser-observed `PRON` argument receives generic PNF alternatives:

```text
entity_reference
eventuality_reference
proposition_reference
```

A subject additionally retains:

```text
expletive_realisation
```

The projection uses parser POS, dependency, morphology, offsets, structural
relations and PNF factor roles. It contains no English pronoun catalogue and no
GWB, Bush, president, Ada or other corpus/fixture vocabulary branch.

## Operational representation

Migration `008_binding_candidate_sets.sql` introduced:

- `pnf.factor_anchor`;
- `resolution.binding_candidate_set`;
- `resolution.binding_compatibility_assessment`;
- `resolution.binding_candidate_member`;
- `resolution.binding_exclusion_summary`;
- `resolution.refinement_candidate_set`;
- `resolution.v_binding_candidate_set_summary`.

Migration `009_structural_binding_index.sql` adds:

- discourse/clause/paragraph/quotation/reporting/coordination anchors;
- normalized `pnf.factor_morphology` rows;
- referential-kind and accessibility-path declarations;
- candidate-set build receipts;
- meet-to-set links;
- the indexed `resolution.query_binding_candidates(...)` parity query.

Migration `010_binding_active_document_fks.sql` moves migration 008's document
foreign keys from the superseded `compiler_document` carrier to the active
`corpus.document` operational table.

Migration `011_operational_document_build_reuse.sql` records exact-key completed
v0.7 document builds and their demand refs. An unchanged rerun returns those
refs without reparsing or rebuilding, including documents with zero candidate
sets or zero demands.

One reference-factor revision and referential type produce one candidate set.
Compatible candidates are member rows. Predictable inaccessible/incompatible
negative cases are retained as deterministic reason counts instead of duplicate
evidence payloads.

## Structural accessibility

The fixed two-sentence rule is absent from the operational path. The versioned
declaration permits typed paths such as:

```text
same clause
governing clause
preceding coordinated clause
same sentence
preceding discourse unit
reporting/content boundary
preceding paragraph
preceding document unit
```

A 64-member computational limit is applied only after accessibility and
compatibility. It limits materialization; it does not define discourse meaning.

The Python candidate set and PostgreSQL indexed query must return identical
member factor refs. A mismatch aborts the document transaction.

## Refinement and revision identity

A reference factor retains one alternative per candidate set:

```text
semantic.binding_candidate_set:<set-ref>
```

It does not retain one complete factor alternative per member.

Refinement receipts contain:

```text
prior factor revision
resulting factor revision
candidate-set refs
added/retained/rejected alternative refs
residual transitions
non-retired evidence refs
```

Removed pairwise alternatives cannot remain listed as added. Only retired
pairwise binding evidence is removed; recurrence, local-type, constraint and
other local evidence remains linked.

Factor revision identity is content-addressed. Its derived self-reference and
identity-contract metadata are excluded from the payload hash. Legacy v0.6
transition-receipt IDs are normalized before candidate build keys are formed.
Persistence rejects an explicit canonical revision ref that disagrees with the
factor content.

## Compatibility boundary

`compact_binding_artifacts(...)` still accepts an expanded pairwise carrier for
old explicit exports and synthetic compatibility tests. PostgreSQL compilation
uses `compile_document_operational(...)`, which never calls or materializes
`_binding_evidence`.

## Build identity and reuse

A candidate set is keyed by:

```text
reference factor revision
+ document PNF graph/index revision
+ accessibility declaration revision
+ compatibility declaration revision
+ referential type
```

A complete document build is keyed by:

```text
document identity
+ content hash
+ compiler context/declarations
+ postgres-semantic-compiler:v0_7
```

External snapshots are not inputs and cannot invalidate local candidate-set or
document builds.

## Authority boundary

This tranche performs no:

- antecedent selection;
- coreference or identity closure;
- proposition-truth decision;
- event-occurrence decision;
- expletive inference from an empty candidate search;
- external registry request;
- readiness or promotion action.

## Validation and measurement

`reference-binding-mini` proves subject/object entity reference, eventuality
reference, proposition reference, zero-member expletive-compatible sets,
morphology exclusions, structural accessibility beyond two sentences,
set-native refinements, canonical revisions and exact-key rerun reuse.

`scripts/benchmark_binding_candidate_sets.py` compares an explicit expanded
legacy compilation with the complete set-valued projection.

`scripts/report_binding_candidate_storage.py` reports semantic cardinality and
PostgreSQL relation, TOAST and index sizes independently. The former 174 MB JSON
artifact is not treated as a PostgreSQL storage measurement.
