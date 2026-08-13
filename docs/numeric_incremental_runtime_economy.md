# Numeric incremental runtime economy

This document instantiates the Agda runtime-economy constitution in SensibLaw.
The governing rule is simple: once spaCy has emitted durable parser observations,
ordinary semantic work should be numeric, sparse, incremental and reopenable.

## Numeric immediately after parsing

Migration 040 already gives tokens numeric `token_id`, `orth_symbol_id`,
`lemma_symbol_id`, `pos_symbol_id`, `dependency_symbol_id` and `head_token_id`.
Migration 089 removes repeated text predicates from the expensive 083
parser/object anchor by compiling `PROPN`, `NOUN`, `appos` and `PERSON` into a
tiny numeric constant cache. Migration 090 similarly compiles alias cue symbols
before document-scale identity-evidence joins.

`src/text/phrase_cues.py` no longer accepts regex-like semantic cues. Finite cue
languages use `NumericCueAutomaton` over integer SymbolIds. Literal text matching
is retained only as an explicit boundary compatibility helper.

Algorithmic motivation: Alfred V. Aho and Margaret J. Corasick, *Efficient
string matching: an aid to bibliographic search*, Communications of the ACM
18(6), 333–340 (1975), DOI `10.1145/360825.360855`. The citation motivates the
finite-state matching strategy; runtime complexity is still measured locally.

## Persistent parser geometry

Short dependency ancestry is compiled once into
`semantic_parser_token_ancestor`, bounded to depth eight. PNF region/interface
ancestry continues to reuse the earlier numeric ancestor machinery from 043.
This prevents repeated graph walks from becoming an accidental semantic tax.

## Sparse structural support

`semantic_pnf_object_token_support` remains the canonical parser→PNF seam.
Migration 089 adds the reverse composite index and
`semantic_pnf_structural_support_fanout_v1`. Support is not allowed to turn into
an all-token × all-object relation: fanout is measurable and should remain small
before support participates in identity/factor joins.

## Lazy relational horizons

`semantic_pnf_horizon_work_queue` makes H3/H6/H9 execution lazy rather than only
logically staged. Every demand starts at H3. H6 is enqueued only after unresolved
H3 work survives; H9 only after unresolved H6. Existing deductive
`semantic_pnf_frontier_resolution` can settle work. Inductive preference cannot.

`NumericIncrementalRuntimeStore.record_evidence` refuses H6/H9 evidence for a
demand that has not been explicitly queued at that horizon.

## Incremental recomputation

`semantic_pnf_reverse_dependency` maps changed numeric sources to affected
demands. Evidence insertion records its reverse dependency and wakes only the
corresponding incremental frontier. Whole-document and whole-corpus rebuilds
remain recovery/audit operations rather than the normal update semantics.

Absence of evidence is not contradiction evidence. The incremental wiring has no
refutation path; semantic refutation remains evidence-indexed in migrations
086–087.

## Hot/cold execution state

Append-only execution/admissibility/preference history remains authority.
Migration 089 maintains small current-state projections transactionally so
ordinary reads do not repeatedly execute `DISTINCT ON` across a lifetime of
history. `rebuild_numeric_pnf_candidate_current_state` reconstructs them from
history and `verify_numeric_pnf_candidate_current_state` compares the maintained
projection against the authoritative rebuild.

This is the runtime counterpart of the exact minimal-residual work in the Agda
reference: keep only what is required for current/future execution hot, retain
full provenance cold, and measure receipt/reopening cost rather than assuming
that a larger active state is safer.

## Frequency-adaptive physical symbol codes

Canonical `semantic_symbol.symbol_id` is stable semantic identity and is never
renumbered by frequency. `semantic_symbol_frequency_codebook` is a separate
physical codec projection: common symbols can receive low compact codes while
rare symbols receive larger codes. Rebuilding that codebook cannot alter a
semantic join.

This captures the useful part of the intuition that extremely common tokens
such as articles should have cheap physical encodings without making database
identity dependent on corpus frequency.

## Relative eight-way address geometry

`relative_octant_codec.py` represents one parent-relative eight-way refinement
step with exactly three bits and packs a path densely (`ceil(3n/8)` bytes).
That is an address-code result only. It does **not** claim that a complete PNF
cell, provenance receipt or semantic payload occupies one byte.

## Corpus-local entity learning

`semantic_pnf_corpus_entity_label_cache` is maintained from currently admitted
identity witnesses. The key is `(label_symbol_id, canonical_entity_id,
authority_class)`, so one surface label may continue to name many entities.
Lookup is a cheap proof-bearing candidate cache, not identity admission.

As a corpus accumulates repeated entities and vocabulary, later documents should
need less unresolved resolution work. `CorpusLearningEconomy` in Agda proves the
non-increase of the declared work bound under its reuse assumptions; migrations
089–091 record the corresponding empirical token-normalised work and provide an
exact same-token non-increase assertion.

## Context-qualified Wikidata/world cache

Wikidata entities are represented in the hot path as `(provider_id=1,
provider_numeric_id)`. A label caches a **fibre** of world candidates. A mention
attachment requires a context witness belonging to that token and can select one
candidate from that fibre. A previous Springfield attachment therefore does not
globally turn every future `Springfield` token into the same Q item.

The legacy external authority text identifier remains only at the external
protocol boundary. `admit_numeric_pnf_wikidata_identity_alignment` reconstructs
`Q<number>` there and delegates to the existing proof-relevant external identity
admission path.

## Workload scale

Tokens are the primary cross-document throughput denominator. Notes, chats,
articles, chapters and books may still be scheduling units, but document count
alone is not a comparable scale measure.

`benchmark_reopenable_runtime.py` now emits token count, tokens/s, work/token,
retrieval reduction and structural-support fanout using structured PostgreSQL
`EXPLAIN ... FORMAT JSON` rather than regex-parsing plans.

`record_numeric_pnf_corpus_reuse_measurement` and
`report_corpus_learning_curve.py` expose per-document and cumulative token-scale
curves. The important empirical questions are:

- does unresolved work/token fall as corpus reuse grows?
- does semantic tokens/s rise or remain stable?
- does adding one document remain approximately local rather than causing
  corpus-wide work?
- does post-parser time remain a small fraction of spaCy time on the same token
  workload?

## Partitioning

Migration 089 deliberately does **not** partition the large history/support
relations. `semantic_pnf_partition_readiness_v1` reports row/byte scale first.
Compact relative representations, hot projections and incremental wakeups should
be exhausted before paying PostgreSQL partition-management costs.
