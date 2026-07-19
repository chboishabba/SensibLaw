# GWB local PNF binding baseline

Date: 2026-07-19
Compiler contract: `postgres-semantic-compiler:v0_7`
Status: reporting and proof runner implemented; full source corpus is local-only in the current remote checkout

## Purpose

The GWB baseline must describe the six public-bios documents alone rather than
mixing them with generic integration fixtures. It measures the shape of local
ambiguity after set-valued PNF binding without ranking or selecting antecedents.

The measured construction is:

```text
GWB corpus occurrence
→ document-local PartialPNF factors
→ reference-factor revisions
→ BindingCandidateSet(reference revision, referential type)
→ compatible member rows + compact exclusion summaries
→ immutable refinements
→ revision-linked demands
```

Candidate membership is not identity closure. A singleton set is not a resolved
antecedent, and a zero-member set is not evidence of expletivity.

## Corpus-scoped semantic ledger

`scripts/report_binding_candidate_storage.py --corpus-ref ...` now reports:

- document occurrences and distinct documents;
- factors, factor revisions, refinements, refined factors and revision locality;
- candidate sets and members;
- zero, singleton, `2..5`, `6..20` and `>20` member buckets by referential type;
- candidate-set counts by referential type and parser-supported syntactic role;
- exclusion-summary rows and actual excluded-candidate totals by reason;
- accessible candidate count and compatibility-retention rate;
- demand totals, open state, revision linkage and candidate-set linkage;
- demand distributions by budget, scope, subject kind and formal role;
- document build and occurrence-reuse state;
- absence of operational `typed_binding_candidate` pairwise evidence.

Physical PostgreSQL relation, TOAST and index sizes remain explicitly database-wide.
They are not presented as corpus-scoped storage attribution.

## Full-corpus proof runner

`scripts/run_gwb_binding_baseline.py` expects six source documents and runs:

```text
first PostgreSQL compilation
→ corpus-scoped ledger
→ exact second compilation
→ reuse and cardinality invariants
```

The proof requires:

- six compiled documents and zero failures;
- nonempty candidate-set construction;
- one completed candidate-set build per candidate set;
- all demands attached to factor revisions;
- zero pairwise binding evidence rows;
- unchanged candidate sets, members, factor revisions, refinements and demands on rerun;
- all six occurrences changing from `compiled` to `reused_compilation`;
- unchanged completed document-build count.

The demand-reference population is represented by a deterministic SHA-256 digest,
not repeated into the JSON ledger.

## Current source-corpus boundary

The workstation run used:

```text
demo/ingest/gwb/public_bios_v1/raw
```

with six local HTML documents. That directory is not tracked in the current remote
SensibLaw checkout. The tracked `.tmp_phi_gwb.sqlite` file is an intact derived
semantic/linkage store, but it contains only a small emitted event/relation slice;
it is not the six-document canonical-text corpus and cannot lawfully substitute for
it.

The GitHub Actions `gwb-proof` job therefore has two explicit states:

```text
source corpus present
→ compile all six documents twice
→ emit full corpus-scoped ledger

source corpus absent
→ emit source_corpus_unavailable_in_checkout receipt
→ do not infer statistics from the derived SQLite store
→ do not claim the full GWB proof passed
```

The focused parser/PNF/PostgreSQL tests remain independent and must stay green in
both states.

## Authority boundary

This measurement layer performs no:

- antecedent ranking or selection;
- identity closure;
- event occurrence decision;
- proposition truth decision;
- external evidence acquisition;
- readiness or promotion action.
