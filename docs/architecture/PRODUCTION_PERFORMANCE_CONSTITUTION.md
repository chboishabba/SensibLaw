# Production performance constitution

This document fixes the optimisation priority for the production ITIR/SensibLaw
compiler. It is deliberately stricter than a list of possible speedups.

The north-star execution contract is:

```text
parse once
→ compile numerically
→ retain proofs
→ reopen locally
→ reuse forever
```

A change is high priority when it moves normal production execution toward that
contract. Making a compatibility representation faster is useful only when the
compatibility representation cannot yet be removed from the critical path.

## 0. Optimise the longest absolute horizons first

Optimisation attention is ordered by **absolute production wall-time exposure**,
not by percentage speedup or ease of implementation.

A minutes/hours phase outranks a seconds-scale kernel while both remain on the
critical path. A 50% improvement to a 2-second kernel does not outrank removing
20 minutes from a compatibility, corpus, persistence, or orchestration phase.

The first question for every long phase is still architectural:

```text
Does normal production need to perform this phase at all?
```

If no, remove or bypass it. If yes, reduce its work before parallelising it.
Seconds/subsecond kernels remain worth improving, especially when they scale per
document or per edit, but they are secondary while minutes/hours horizons exist.

`src/runtime/performance_attention.py` provides the executable ranking rule and
classifies measured phases as `hours`, `minutes`, `seconds`, or `subsecond`.
The ranking does not claim that the full measured duration is removable; it only
prevents optimisation attention from drifting toward diminishing-return kernels.

## 1. Highest priority: spaCy → numeric machine

The desired ordinary path is:

```text
source bytes/text
      ↓
ingestion boundary
      ↓
spaCy
      ↓
numeric observation tape
      ↓
numeric structural carrier
      ↓
numeric PNF closure / demands
      ↓
H3 residual
      ↓
H6 residual
      ↓
H9 residual
      ↓
typed PostgreSQL authority
```

Everything to the right of spaCy has to plead its case if it remains a semantic
working representation as:

- text or string comparison;
- regex;
- JSON/JSONB;
- document-sized Python dictionaries;
- repeated canonical serialisation;
- repeated content hashing of an identity already carried by a ref;
- unbounded graph reconstruction.

The relevant executable contract is
`src/runtime/numeric_hot_path_constitution.py`.

## 2. Make the strict numeric compiler the normal path

The rich operational compiler remains useful as an audit/reference/parity
implementation, but it must not remain the production architecture merely
because some provenance is still emitted there first.

The migration direction is:

```text
old
numeric parser
→ rich operational graph
→ operational provenance
→ numeric bridge
→ numeric PNF

new
numeric parser
→ numeric PNF + trigger/target/evidence provenance directly
```

A production feature is incomplete while it requires the compatibility graph to
reconstruct information that was available structurally at the numeric producer.

## 3. JSON is a boundary debt, not a hot-path encoding

`docs/architecture/JSON_SIN_BIN.md` remains authoritative for the repository-wide
policy.

The current manifest digest is a legacy identity contract. Where that exact
identity must be preserved, one canonical JSON pass is tolerated at the explicit
identity boundary. It is not permission to use JSON as a semantic carrier.

The preferred sequence is:

```text
producer
→ establish canonical identity once
→ immutable producer seal / digest receipt
→ typed or numeric in-process consumers
```

not:

```text
object
→ dict
→ canonical JSON
→ SHA
→ dict/envelope
→ canonical JSON again
→ SHA again
→ semantic consumer
```

The ordinary production target is therefore:

```text
JSON transformations in semantic execution ≈ 0
```

JSON may still exist for explicit import/export, audit, external protocol, or a
versioned legacy identity boundary. Such use requires a named boundary permit,
not an implicit convenience import.

## 4. Incremental economy is non-negotiable

For a controlled identical workload/configuration, accumulated reusable corpus
structure must not make the same semantic work more expensive:

```text
W_after <= W_before
```

This claim is conditional on exact workload/config identity. A cold run cannot
prove it.

Runtime execution should have the shape:

```text
new evidence
→ reverse dependencies
→ affected demands
→ affected factors
→ affected projections
```

not document- or corpus-wide recomputation.

Likewise H3/H6/H9 are execution horizons, not just labels:

```text
all active demands
      ↓ H3
only H3 residual
      ↓ H6
only H6 residual
      ↓ H9
```

No H6 work is owed by an H3-sufficient consumer. No H9/world work is owed by an
H6-sufficient consumer.

Missing evidence, cache misses, missing context, and zero-result provider probes
are reopen/escalation conditions. They are never semantic refutation:

```text
absence of evidence != evidence of absence
```

## 5. Performance acceptance

The enduring ordinary-path target is:

```text
T_post-parser << T_spaCy
```

with an aggressive acceptance target for controlled warm/local execution:

```text
T_post-parser <= 0.10 * T_spaCy
```

This ratio may be reported only when both quantities are explicitly measured.
Wall-time subtraction is not a parser measurement.

The canonical cross-document denominator is tokens, not documents. Benchmarks
should report, where measurable:

- tokens and tokens/s;
- semantic work units/token;
- wall and CPU time/token;
- peak memory/token;
- parser/post-parser ratio;
- new work versus reused work;
- H3/H6/H9 population and residual fractions;
- reopened fibres;
- provider/network calls;
- semantic digest parity.

The executable single-run/paired-run assessment lives in
`src/runtime/performance_constitution.py`.

A single cold replay can prove completion and semantic parity. It cannot prove:

- incremental economy;
- delta-local recomputation;
- same-domain corpus learning;
- corpus-scale linearity.

Those require paired or scaling observations.

## 6. Required benchmark families

Performance work should converge on four distinct measurements:

```text
T_cold
T_exact-replay
T_small-edit
T_same-domain-new-document
```

The desired architecture may legitimately have a nontrivial cold compile while
being exceptionally cheap to reopen or update. Optimising cold execution at the
expense of reuse/reopenability is a regression.

Corpus scaling should additionally measure increasing token populations, e.g.
10, 100, 1,000, 10,000 documents, without treating document count itself as the
work denominator.

For corpus size N, we want an increasingly broad observed range in which total
work remains approximately linear in new input and incremental addition remains
approximately delta/document local rather than corpus-sized.

## 7. Parallelism and SIMD come after work reduction

Once the production carrier is predominantly:

- integer IDs/codes;
- small enums;
- sorted integer vectors;
- bitsets;
- packed relative addresses;
- sparse reverse-dependency frontiers;

then native/SIMD kernels become natural for intersections, masks, prefix/delta
decode, candidate filtering, and dependency propagation.

Likewise parallelism should operate over immutable independent work fibres with
a deterministic canonical commit. It must not be used to hide avoidable rich
carrier work.

The rule is:

```text
first reduce work
then vectorise / parallelise the reduced work
```

## 8. Owner-wave correctness seam

Different owner keys are not automatically independent. General parallel owner
reduction requires frozen-wave semantics:

```text
K_n = frozen known factors
D_n = dirty owner frontier

for o in D_n, evaluate R_o(K_n) independently
→ canonical commit
→ K_{n+1}
→ wake revdeps(K_{n+1} Δ K_n)
```

The existing dependency-free coalescing optimization is deliberately narrower.
The general owner-wave theorem/runtime should not outrank removing compatibility
work that the numeric production compiler should not execute at all.

## 9. World/H9 remains last and sparse

World resolution is consumer-observable residual work only.

Normal policy is:

```text
local proof/cache
→ cached world evidence
→ snapshot tier where freshness permits
→ live provider only for the remaining required residual
```

A label may own many world candidates. A prior Springfield candidate does not
globally collapse later Springfield mentions. Mention-local context/evidence
selects or pressures a candidate fibre; preference is not identity proof.

Provider/cache absence never closes negatively.

## 10. Priority deliverables

In order:

1. Numeric production compiler completeness, including native occurrence
   provenance needed by downstream consumers.
2. Numeric compiler becomes the default production path; rich operational
   compilation becomes audit/reference/compatibility.
3. Remove remaining nonnumeric hot-path carriers. JSON/regex/text survive only
   behind explicit defended boundaries.
4. Make H3→H6→H9 physically lazy.
5. Make reverse-dependency recomputation delta-local and reopenable.
6. Demonstrate proof-bearing corpus reuse and controlled work non-increase.
7. Establish cold/replay/edit/same-domain and corpus-scale token-normalised
   curves.
8. Formalise and implement dependency-correct frozen owner waves.
9. Apply native/SIMD kernels to the remaining measured numeric kernels.
10. Keep H9/world work sparse, cached, context-bearing, and consumer-demanded.

Within every numbered deliverable, measured minutes/hours phases outrank
seconds/subsecond kernels until the longer phase is removed, bypassed, or shown
not to lie on the relevant production critical path.

## 11. Decision rule for optimisation PRs

Before optimizing an expensive operation, ask:

> Does normal production need to perform this operation at all?

If the answer is no, remove/bypass it rather than making it faster.

If the answer is yes because it is a compatibility or identity boundary, perform
it once, preserve its receipt, and keep it out of downstream semantic execution.

That is the bigger meaning of the current JSON/carrier work: the deliverable is
not faster JSON. It is a compiler whose normal semantic execution no longer
needs JSON.
