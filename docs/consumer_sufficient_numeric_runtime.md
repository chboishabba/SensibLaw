# Consumer-sufficient numeric runtime

This stacked runtime tranche instantiates the Agda freeze-point from `dashi_agda`
PRs #521, #530, #531 and #533 on top of SensibLaw's existing reopenable numeric
PNF carrier.

The implementation does not create a second resolver. PostgreSQL's existing
candidate/demand/evidence/identity/factor relations remain semantic authority.
The new structures are typed evidence, consumer-indexed execution projections,
and rebuildable physical caches around that authority.

## Effective migration surface

Migrations 092-095 are intentionally read in lexical order. The later migrations
harden the first implementation cut:

- 092 introduces exact hot-state verification, typed contextual requirements,
  consumer sufficiency receipts, controlled-workload identity, and packed tape
  storage.
- 093 adds controlled reuse recording and two-phase tape registration.
- 094 replaces the initial broad context comparison with a label-scoped numeric
  join and replaces the first consumer horizon function with an independent
  `(consumer, query, policy)` queue. The global proof-required queue is never
  completed merely because one consumer can stop.
- 095 preserves contextual ties and certificate revision. Only a unique top,
  fully positively witnessed contextual candidate may be automatically attached;
  ties stay unresolved. Sufficiency is append-only/revisioned and can be
  withdrawn.

The effective post-095 laws are described below.

## Contextual world fibres

A lexical label still maps to a fibre of cached world candidates. Each candidate
may carry typed requirements:

```text
(world entity, axis kind, required symbol, polarity)
```

A mention-local context witness carries typed observed coordinates:

```text
(context witness, axis kind, observed symbol, polarity)
```

Comparison is numeric and mention-scoped. A missing coordinate is `unknown`, not
negative evidence. Contradiction requires an explicit opposite-polarity
observation on the same axis/symbol coordinate.

The database computes support, contradiction, unknown count, and signed margin.
A candidate is fully satisfied only when every declared requirement is positively
witnessed and none is contradicted or unknown.

Automatic attachment requires a unique top fully satisfied candidate. Equal top
candidates remain unresolved. Attachment is mention-local preference state and
never calls the external identity-admission function; canonical Wikidata/world
identity still requires the existing proof-producing admission lane.

The attachment function also verifies that the context witness belongs to the
mention token, that token and context region share run/document identity, that the
token lies within the region, and that the label symbol is the token's numeric
orthographic or lemma symbol.

## Consumer/query/policy horizon execution

The global H3/H6/H9 queue remains the proof-required semantic lane.

Consumer execution has its own queue keyed by:

```text
(demand, consumer, query, policy, horizon)
```

A query/future/policy certificate may stop this queue without changing the
underlying demand state or suppressing another consumer's work.

Certificate kinds are:

1. exact query factorisation;
2. restricted-policy safety;
3. full future/dynamic safety.

For a query-only consumer, kinds 1 or 3 can stop escalation. Once a non-empty
policy may act, kind 1 alone is insufficient: kind 2 or 3 is required.

Certificates are append-only revisions. The latest revision of each certificate
kind is authoritative for the current execution projection and may be marked
withdrawn/superseded. Earlier receipts remain present.

Consumer-specific reverse dependencies use the same sparse numeric source ids as
the global incremental lane but add consumer/query/policy coordinates. New
evidence can therefore wake only the affected consumer fibres rather than a
whole document/corpus.

## Controlled corpus learning

Chronological order and equal token count are not workload identity.
The theorem-facing measurement path requires:

- `workload_ref`;
- 32-byte workload digest;
- consumer reference;
- 32-byte compiler-configuration digest;
- unchanged token carrier;
- unchanged fixed numeric work.

Only then can unresolved-resolution work before/after be compared under the
Agda non-increase contract.

`controlled_workload_digest()` binds the canonical authority digest to consumer,
query and policy so different uses of the same text do not silently become one
benchmark workload.

## Exact hot/cold projection

`verify_numeric_pnf_candidate_current_state()` now checks extensional equality in
both directions for execution, admissibility and preference. A stale extra hot
row therefore fails verification just as a missing hot row does.

Demand foreign keys are added to the three hot tables for new/changed rows while
remaining `NOT VALID` for upgrade tolerance of any historical orphan.

## Numeric observation tape

PostgreSQL parser rows remain authority. Codec v2 packs a rebuildable physical
projection containing:

- token and sentence ids;
- local token ordinal and character span;
- orthographic and lemma symbol ids;
- POS, tag and dependency symbol ids;
- morphology-set id;
- head token id;
- lemma/POS/tag/dependency annotation-origin ids.

The origin ids are essential: parser output and an orthographic/POS fallback must
not collapse merely because their resulting symbol ids happen to match.

The codec uses unsigned varints, ZigZag deltas for signed coordinate differences,
and relative head-token deltas. It asserts `decode(encode(rows)) == rows` in
Python and records SHA-256 digests for both the canonical row carrier and packed
payload.

Tape registration starts with `exact_roundtrip_verified = false`. Python must
independently decode and compare the payload before calling the verification
function. A packed row is a cache, never a semantic authority replacement.

Codec v2 currently writes canonical `SymbolId` values directly. The consumer
store rejects non-zero frequency-codebook revisions so metadata cannot falsely
claim frequency remapping that was not actually encoded. A future codebook-aware
codec must add its own exact decode proof/receipt before exploiting physical
frequency codes.

## Validation boundary

No GitHub Actions or CodeRabbit run is part of this tranche. The migrations and
Python have source/contract regressions in-tree, but a real PostgreSQL migration
application and corpus benchmark are still required before claiming database or
performance certification.
