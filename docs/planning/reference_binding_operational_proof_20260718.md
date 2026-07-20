# Generic PNF reference-binding operational proof

Date: 2026-07-18
Compiler contract: `postgres-semantic-compiler:v0_7`
Base implementation checkpoint: `3f563f2`

## Correction

`gwb-mini` remains a useful corpus and PostgreSQL smoke proof, but it is not a
proof of local reference binding. Its texts do not exercise parser-observed
pronominal arguments, nonempty candidate sets, proposition/eventuality binding,
or the distinction between an empty candidate search and an expletive branch.

The compiler now has a separate corpus-neutral proof:

```text
tests/fixtures/corpora/reference-binding-mini/
```

It contains:

```text
Ada entered the hall. She spoke.
Ada greeted Lin. Lin thanked her.
The storm intensified overnight. It caused flooding.
The report alleged that the bridge failed. It was disputed.
It was raining.
```

These names and sentences are fixture data only. The implementation contains no
Ada, Lin, Bush, GWB, president, pronoun-word list, or corpus-specific semantic
branch.

## PNF-centred construction

The operational path is:

```text
one parser observation graph
→ parser-observed argument factors
→ pronominal PNF reference alternatives
→ structural factor anchors and morphology rows
→ one BindingCandidateSet per reference revision/type
→ normalized member/assessment/exclusion rows
→ set-native typed meets
→ immutable factor revision deltas
→ revision-linked local/external demands
```

A parser-observed `PRON` argument receives generic alternatives:

```text
entity_reference
eventuality_reference
proposition_reference
```

A subject additionally retains:

```text
expletive_realisation
```

No English lexical catalogue is consulted. The parser's POS, dependency,
morphology, offsets, factor kind and structural position are the input.

## Direct candidate-set generation

PostgreSQL operational compilation no longer derives candidate sets by
compacting pairwise `LocalEvidence` rows. `BindingCandidateSet` is generated
directly from the annotation/PNF graph.

Pairwise binding evidence remains accepted only as a compatibility input for
older explicit exports and synthetic tests. It is removed before operational
persistence.

Each set is keyed by:

```text
reference factor revision
+ document PNF graph/index revision
+ accessibility declaration revision
+ compatibility declaration revision
+ referential type
```

Zero-member sets are persisted. They mean only:

```text
no compatible member under this declared local build
```

They do not mean:

```text
expletive
non-referential
resolved
contradicted
```

## Structural accessibility

The old fixed two-sentence rule is not part of the operational path. The
versioned declaration uses structural paths:

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

The implementation applies a 64-member computational cap only after structural
accessibility and type/morphology compatibility. The cap limits materialization;
it does not define discourse semantics.

Migration `009_structural_binding_index.sql` adds:

```text
factor structural-position indexes
normalized factor morphology
referential-kind declarations
accessibility-path declarations
candidate-set build receipts
meet-to-candidate-set links
resolution.query_binding_candidates(...)
```

The PostgreSQL compiler validates every persisted candidate set against that
indexed SQL query in the same transaction. A membership disagreement aborts the
document write.

## Refinements and revision identity

A reference factor revision adds one alternative per candidate set:

```text
semantic.binding_candidate_set
```

It does not add one complete factor alternative per candidate member.

Operational refinement receipts contain:

```text
prior factor revision
resulting factor revision
candidate-set refs
added/retained/rejected alternative refs
residual transitions
non-retired evidence refs
```

Removed pairwise alternatives cannot remain recorded as added alternatives.
Only retired pairwise binding evidence is removed; unrelated local evidence is
preserved.

Factor revision identity excludes its own derived
`metadata.factor_revision_ref`. If an explicit revision reference disagrees with
canonical content, persistence fails closed.

## Proof gates

The pure proof requires:

- subject and object pronominal arguments;
- nonempty entity candidate sets;
- nonempty eventuality candidate sets;
- nonempty proposition candidate sets;
- zero-member entity/eventuality/proposition sets for `It was raining`;
- an expletive alternative independent of candidate-set emptiness;
- no pairwise binding alternatives in resulting factors;
- no pairwise binding evidence in the operational artifact;
- local demands linked to candidate sets and resulting factor revisions;
- morphology mismatches represented as exclusion assessments;
- structural accessibility beyond a fixed two-sentence window;
- deterministic/idempotent builds.

The live PostgreSQL proof additionally requires:

- all five documents persisted without failure;
- nonzero member counts for entity/eventuality/proposition sets;
- one or more zero-member sets;
- no persisted `typed_binding_candidate` evidence rows;
- one immutable build row per candidate set;
- indexed SQL/Python membership parity;
- unchanged build count and demand refs on rerun.

## Authority boundary

This tranche performs no:

- antecedent selection;
- entity identity closure;
- event-occurrence closure;
- proposition-truth evaluation;
- expletive inference from an empty set;
- cross-document reconciliation;
- external snapshot lookup;
- readiness or promotion action.

## Next work after the proof passes

```text
nominal-description and modifier-scope refinement
→ document-local binding resolution proof
→ post-refinement demand quality review
→ Wikidata snapshots
→ WorldMonitor snapshots
→ typed external reconciliation
→ readiness
```
