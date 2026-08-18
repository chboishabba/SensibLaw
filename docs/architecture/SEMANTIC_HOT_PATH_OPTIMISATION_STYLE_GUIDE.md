# Semantic Hot-Path Optimisation Style Guide

This guide is the default review standard for performance work in SensibLaw's
numeric PNF / ITIR execution lanes. It turns the optimisation lessons from the
large-corpus replays into repository policy.

The governing principle is:

```text
preserve the semantic fibre
→ project only what the consumer needs
→ keep the projection set-wise and numeric
→ retain residual/provenance needed to reopen
→ do not reconstruct information the producer already possessed
```

Performance changes do not receive semantic authority merely because they are
faster. They are admissible only when the existing observation, provenance,
residual, identity and failure boundaries are preserved.

## 1. The default complexity target is active-carrier work

For an execution step with active frontier `F` and touched dependency edges `E`,
the desired physical work shape is:

```text
W_next = O(|F| + |E|)
```

not work proportional to the complete document, corpus, historical event table,
or all materialized semantic possibilities.

A performance review should therefore ask first:

1. what is the semantic input carrier for this operation?
2. what is the consumer of its output?
3. which rows/edges can actually affect that consumer?
4. why is every touched relation inside that dependency closure?

If the implementation cannot answer those questions, measurement alone is not a
sufficient optimisation argument.

## 2. Preserve batches across the physical boundary

A set-wise producer must not be decomposed into row-wise database work and then
reassembled unless there is an explicit semantic reason.

### Preferred

```text
COPY / INSERT relation
→ statement-level transition table
→ set projection / join / upsert
```

### Sin-bin candidate

```text
COPY / INSERT relation
→ FOR EACH ROW trigger
→ SELECT context for one row
→ INSERT/UPDATE derived rows
→ repeat N times
```

Likewise in Python:

```text
one numeric batch
→ executemany(UPDATE ... WHERE id = ...)
```

is a review smell when the same update is expressible as one relational
projection.

Recent examples motivating this rule include:

- parser-token COPY followed by one sentence-id lookup per token;
- parser-token COPY followed by one dependency-head UPDATE per token;
- parser-sentence COPY followed by one region/work trigger invocation per
  sentence;
- set-wise demand insertion followed by one procedural provenance reconstruction
  per demand;
- demand insertion followed by row-level constraint and H3 queue triggers.

The correct question is not "is the row query indexed?". It is "why did a batch
become N queries at all?"

## 3. Producer-native information must flow forward

Do not throw away a relation at the producer boundary and search the materialized
graph to recover it immediately afterwards.

If producer `P` already owns a bounded fibre containing the coordinates needed by
consumer `C`, prefer:

```text
P fibre
├─→ semantic materialization
└─→ C projection / provenance
```

over:

```text
P fibre
→ semantic materialization
→ forget producer relation
→ global/local search
→ reconstruct C projection
```

The second form is acceptable only as a generic compatibility/fail-closed path
for producers that genuinely do not possess the stronger coordinates.

For an optimized producer-native path, the required semantic law is extensional
agreement with the defensive reconstruction:

```text
direct_projection(P) == reconstruct(materialize(P))
```

under the same uniqueness and ambiguity rules.

## 4. Numeric after the parser boundary

Once spaCy has emitted parser observations, semantic hot-path code is numeric by
default.

Preferred carriers include:

- `BIGINT` token, symbol, object, factor, demand, interface and provider IDs;
- `SMALLINT` enum/state/horizon/role codes;
- typed binary digests for stable identity;
- compact integer automata for lexical cue recognition.

Text, regex and JSON require an explicit defended boundary capability such as:

- ingestion/source parsing;
- parser adapter;
- external protocol;
- human-readable export/audit;
- a versioned legacy identity contract.

They are not normal semantic execution carriers.

A string-valued join or regex in a post-parser semantic kernel should therefore
be presumed guilty until it demonstrates why the equivalent numeric coordinate
cannot be supplied or derived once at the boundary.

## 5. A leaf is not a parent frontier

Sharing an interface type does not authorize every reducer on every topology
node.

Distinguish at least:

```text
canonical leaf
canonical parent frontier
overlapping/evidence fibre
```

A producer-complete sentence leaf must not invoke a parent-frontier reduction
merely because both use `semantic_pnf_interface`.

Reduction authority comes from the operation's topology/domain, not from a broad
carrier type.

## 6. Derived carriers should exist only when a consumer exists

Do not eagerly maintain projections whose consumers cannot yet observe them.

Examples include:

- ancestor indexes while parent assignments are still in flux;
- global/visible lookup reconstruction before publication boundaries;
- current-state summaries that ordinary production never reads;
- observability aggregates executed only to decorate a receipt.

Prefer:

```text
source authority
→ bounded changes
→ consumer/publication boundary
→ derived projection once
```

or an exact dirty/delta refresh when the projection must remain live.

Derived-state freshness may use execution-only physical cache identity, but that
identity must never be confused with portable semantic identity.

## 7. Residual/provenance preservation is the optimisation gate

A smaller carrier is not automatically safe.

For a consumer `C`, a compression/projection is admissible only when it preserves
what `C` may validly observe and preserves the residual/provenance required by
permitted future reopening.

Conceptually:

```text
observe_C(X)  == observe_C(pi(X))
residual(X)   == residual(pi(X))     # at the relevant contract boundary
provenance(X) == provenance(pi(X))   # likewise
cost(pi(X))   <= cost(X)
```

If consumer factorization or future dynamic congruence has not been established,
the optimisation status is `indeterminate`, not "probably safe".

This is especially important for:

- same-owner incremental reduction;
- lossy candidate compression;
- context/world-entity caches;
- early deletion of unresolved alternatives.

## 8. Recompute by reverse dependency, not by containment convenience

On an edit or new evidence atom, wake the semantic dependency closure:

```text
changed source/evidence
→ affected demands
→ affected factors/projections
→ bounded downstream frontier
```

Do not reopen a whole paragraph/document/corpus simply because it is an easy
containment boundary.

Conversely, do not claim minimal/local recomputation from a sound but
non-exact closure. Soundness and precision are separate properties.

## 9. Keep history cold and rebuildable hot state small

Append-only evidence/provenance history may be authoritative while ordinary
queries consume a compact current projection.

The hot projection is admissible when it is exactly rebuildable from authority.
It should not require scanning the full history on each ordinary operation.

This gives the preferred architecture:

```text
cold authority/history
→ exact rebuildable current projection
→ active consumer frontier
```

not:

```text
active query
→ DISTINCT/latest reconstruction over all historical rows every time
```

Materialize only surfaces proven hot by measurement.

## 10. Observability is a consumer too

Diagnostics, benchmark counts and audit reports are not free semantic work.

Whole-document/corpus aggregate scans belong behind explicit observability modes
unless production genuinely consumes the result.

Do not make the compiler slower merely so its receipt can report more numbers.

A benchmark must distinguish:

```text
semantic execution work
observability work
```

and should measure the latter independently where material.

## 11. Every hot query should expose cardinality flow

For a slow relation/query record, where possible:

```text
N_input
N_generated
N_retained
N_output
W
T
```

The most useful question is often the amplification ratio:

```text
N_generated / N_input
```

or repeated scan exposure:

```text
rows scanned / unique rows admitted
```

A query can be `O(n)` in abstract notation and still be unacceptable if it
constructs a huge unnecessary intermediate.

The preferred transformation is:

```text
narrow first
→ join second
→ project third
```

rather than broad join followed by late filtering.

## 12. Use PostgreSQL set algebra before adding Python loops

For relational state already in PostgreSQL, prefer:

- `INSERT ... SELECT`;
- `UPDATE ... FROM`;
- transition-table statement triggers;
- `COPY` into bounded stages;
- set-wise joins over staged rows;
- exact dirty tables / reverse-dependency indexes.

Python should not pull an ID family out merely to feed it row-by-row back into
the same database when SQL can express the projection exactly.

This does not mean "put all semantics in SQL". Semantic producer logic may remain
Python/Agda-aligned. The rule concerns physical projection of already-numeric
relations.

## 13. Row triggers must plead their case

A new `FOR EACH ROW` trigger on a bulk semantic table is exceptional.

Its review should state why a statement-level transition-table projection is not
semantically equivalent. Legitimate cases may exist, but "the row trigger was
easy to write" is not one.

For every proposed row trigger answer:

1. Is its output a pure function of the inserted/updated rows?
2. Does it search surrounding materialized state per row?
3. Can the relevant surrounding state be joined once against a transition table?
4. Can the producer provide the needed coordinate directly?
5. What is its invocation count at million-token scale?

If the answers point to set factorization, use a statement trigger instead.

## 14. Reusable physical staging must remain semantically transparent

Temporary/staging tables are execution carriers, not authorities.

They may be reused across transactions when:

- reset before use;
- no semantic identity depends on their physical lifetime;
- all semantic rows are persisted before transaction completion;
- lease/fence/failure boundaries remain unchanged.

Do not broaden transaction atomicity merely to amortize startup costs unless
independent-fibre commutation/factorization has been established separately.

## 15. Parallelism follows semantic independence

Parallelize independent fibres, not arbitrary text chunks.

Execution partitions may run concurrently while remaining fibres over one
shared document graph. Cross-boundary demands are reconciled through the shared
carrier rather than by merging independently invented semantic graphs later.

Before parallelizing a reducer, distinguish:

- different-owner independence/commutation;
- same-owner incremental associativity/homomorphism.

The former does not imply the latter.

## 16. Benchmark in tokens, not documents

A note and a book are not equivalent units of work.

Use tokens (and, where relevant, active frontier rows/edges) as the canonical
cross-document denominator:

```text
time / token
work / token
rows generated / token
```

Document counts remain useful operational metadata, not a scaling denominator.

For recurring-domain corpus learning, compare equivalent workloads before
claiming non-increasing work.

## 17. "Absence of evidence" is not a negative edge

Performance shortcuts must not turn missing cache rows, missing candidate rows,
zero evidence, or a skipped expensive horizon into semantic refutation.

No work performed because no consumer requested H9 means zero work, not evidence
that no world entity exists.

Fail closed to unresolved/indeterminate where evidence is absent.

## 18. Review checklist for hot-path changes

Before merging a performance change, check:

- [ ] semantic authority is unchanged or explicitly migrated;
- [ ] consumer observation is preserved;
- [ ] residual/provenance/reopenability are preserved;
- [ ] numeric execution remains numeric after parser boundaries;
- [ ] a bulk producer does not decompose into avoidable row queries/updates;
- [ ] derived projections are delayed or incrementally dirtied rather than
      globally rebuilt without a consumer;
- [ ] leaf/parent/overlap topology is respected;
- [ ] ambiguity still fails closed;
- [ ] observability cost is not charged to ordinary production unintentionally;
- [ ] cardinality amplification is measured or statically bounded;
- [ ] fallback behaviour is explicit if an optimisation migration is absent;
- [ ] the optimisation has a source/live regression at the appropriate layer;
- [ ] performance claims are separated from semantic correctness claims.

## 19. The practical target

The long-term production goal is deliberately aggressive:

```text
spaCy parses once;
post-parser semantics are a blazingly fast numeric compiled substrate;
new evidence reopens only affected fibres;
repeated-domain compilation becomes cheaper through proof-bearing reuse.
```

A fast system that destroys provenance is wrong. A formally elegant system that
reconstructs every local relation row-by-row at million-token scale is also
wrong. SensibLaw requires both semantic exactness and work-conserving physical
execution.
