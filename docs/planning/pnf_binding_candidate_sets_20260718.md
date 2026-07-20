# Set-valued PNF binding candidates

Date: 2026-07-18
Status: implemented PostgreSQL operational tranche
Document compiler contract: `postgres-semantic-compiler:v0_8`
Reference-binding contract: `postgres-semantic-compiler:v0_7`

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
source bytes
→ declared media adapter
→ canonical text coordinate system
→ parser-observed PNF argument
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

## Canonical source boundary

Raw source bytes and canonical text are separate immutable carriers.

For HTML:

```text
raw HTML bytes
→ HtmlDocumentMediaAdapter
→ tag-free canonical text
→ tokens, licensed spans, annotation graph, PNF and demands
```

The raw HTML remains in `corpus.binary_content`. The adapter-produced text is
stored in `corpus.canonical_content`; every character offset and token range in
the semantic runtime addresses that canonical payload.

The v0.8 operational document identity includes:

```text
raw source content hash
+ canonical text hash
+ media type
+ selected media-adapter revision
+ media-normalization revision
+ document compiler contract
```

This is deliberately stronger than the source-only v0.7 identity. Recompiling a
pre-v0.8 database creates a new immutable operational document rather than
mutating or colliding with a document row whose canonical pointer retained raw
HTML. The old source/document evidence remains inspectable.

Persistence fails closed if:

- compiler and persistence canonical text differ;
- canonical hashes differ;
- the selected adapter differs from the declared capability;
- a licensed mention falls outside canonical character or token coordinates;
- a mention surface differs from the canonical substring at its stored range;
- character and token boundaries disagree.

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
document builds and their demand refs. An unchanged rerun returns those refs
without reparsing or rebuilding, including documents with zero candidate sets or
zero demands.

Migration `012_binding_demand_links.sql` normalizes demand-to-candidate-set links.

Migration `013_canonical_text_coordinate_build.sql` registers the v0.8 document
compiler operation after canonical text, adapter revision and coordinate identity
became explicit build inputs.

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

The document compiler v0.8 and reference-binding algebra v0.7 are distinct
contracts. Canonical-coordinate persistence changed without changing the
meaning or authority of candidate-set membership.

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
operational document identity
+ raw source content hash
+ canonical text hash
+ selected media adapter
+ compiler context/declarations
+ postgres-semantic-compiler:v0_8
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

The live HTML proof seeds a source-only pre-v0.8 document whose canonical payload
is raw HTML, then proves that v0.8:

- preserves that old row unchanged;
- creates a distinct operational document;
- stores clean adapter-produced canonical text;
- keeps raw bytes as source evidence;
- aligns every licensed span surface with the canonical substring;
- persists no markup lexemes;
- reuses the new build exactly on rerun.

`scripts/run_gwb_binding_baseline.py` adds the same coordinate-integrity gates to
the six-document GWB tranche: zero canonical markup documents, zero span-surface
mismatches, zero markup-fragment mentions and zero markup lexemes.

`scripts/benchmark_binding_candidate_sets.py` compares an explicit expanded
legacy compilation with the complete set-valued projection.

`scripts/report_binding_candidate_storage.py` reports semantic cardinality and
PostgreSQL relation, TOAST and index sizes independently. The former 174 MB JSON
artifact is not treated as a PostgreSQL storage measurement.
