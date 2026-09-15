# SensibLaw roadmap: federated materialisation, skeletal corpora, retention and replication

Date: 2026-09-15

## Status baseline

The federation/ZOS tranche is now runtime/formally paid through:

```text
consumer residual
-> acquisition policy
-> eligible local/federated capability
-> progressive acquisition depth
-> existing research recurrence
```

The remaining generic federation seam is cross-machine capability discovery plus admitted typed-job transport.

This roadmap adds a separate storage/materialisation axis. It does not create another semantic authority layer.

## Core distinction

SensibLaw must distinguish:

```text
what can be represented
what must be local now
what should be retained
what may be replicated
what may be reacquired
what counts as authority/evidence
```

These are independent coordinates.

```text
semantic world
!= materialised bytes
!= local cache
!= replica set
!= authority
!= payment
```

## Skeletal corpus

A first-class deployment mode should permit a consumer to retain only a skeletal legal/knowledge graph while authoritative source bytes remain fetchable on demand.

A skeleton may include:

```text
ObjectIdentity
SegmentIdentity
Parent/child hierarchy
Jurisdiction/domain
Temporal/revision coordinates
Named-node/entity anchors
PNF/claim anchors
SourceRole
AuthorityRole
ContentDigest
LocatorSet
AvailabilityState
Evidence/payment history
Conflict/residual state
```

Example legal skeleton:

```text
Act
-> Part
-> Division
-> section 116C
-> proposition/PNF anchors
-> temporal version
-> authoritative locator
```

The full text need not be duplicated locally merely so the graph can point to that section. When a consumer needs an exact quotation, primary-authority review, or reconstruction, the source is reacquired through its identity/locator set.

Required firewall:

```text
segment known
!= segment text currently local
!= proposition paid
```

## Query-indexed adequacy

Use existing `FactorsThrough` / query-indexed projection machinery to decide whether a skeleton is sufficient for a consumer.

Examples:

```text
navigation query
  may factor through skeleton

exact quotation query
  does not factor through skeleton lacking source bytes

primary-authority legal review
  requires verified full source + exact source span
```

Therefore storage sufficiency is consumer-relative rather than global.

## Materialisation policy

Define deployment policy over at least:

```text
consumer class
corpus class
privacy/disclosure class
freshness
latency tolerance
local storage budget
network availability
compute budget
source authority requirements
replication policy
retention policy
```

Representative modes:

### `fullLocal`

Retain full bytes and graph locally. Appropriate for authorised matter bundles, offline work, institutional archival requirements, or repeatedly used sources.

### `selectiveCache`

Retain costly/high-value/frequently used objects while leaving the rest content-addressed and retrievable.

### `skeletonPlusFetch`

Retain graph, provenance, PNF/claim anchors, locator sets and history; fetch source bytes only when a consumer requires them.

### `referenceOnly`

Retain identity + locator + digest + observation/payment history and no durable local source bytes.

### `transientProcessing`

Source bytes may exist only for the duration of an admitted parse/review operation.

## Retention state

Candidate state family:

```text
HotLocal
ColdLocal
ContentAddressedReplica
EncryptedRemoteReplica
ReferenceOnly
TransientOnly
PurgedBytesRetainingReceipt
```

Changing retention state must be append-only/auditable.

If bytes are purged:

```text
prior observation remains historical
prior provenance remains historical
prior review/payment is not silently rewritten
```

If later verification requires bytes which can no longer be retrieved, create a new availability/verification residual.

## Replication

Replication is a physical/availability layer.

```text
replica count
not FactorsThrough truth

replica count
not FactorsThrough semantic authority

replica count
not FactorsThrough evidence payment
```

Public objects may be mirrored through IPFS/content-addressed storage. Private material may be local-only, institutionally encrypted, or selectively replicated under an explicit disclosure policy.

ZKP/on-chain/cloud mechanisms are possible future storage/disclosure mechanisms, but are not roadmap prerequisites until a concrete privacy/verification consumer requires them.

## Obsidian/personal knowledge deployment

SensibLaw should not require a second mandatory content mirror for a user who already has a canonical vault.

Minimal mode:

```text
Obsidian vault = source bytes
SensibLaw = node/ref graph + PNF + provenance + residuals + suggested links/tags
```

Optional backup mode may replicate encrypted note objects or DB state.

The graph remains useful even where note bodies stay exclusively in the source application.

## Legal/CLC deployment

For a matter:

```text
private matter bundle -> usually local/restricted
public legislation/cases -> skeletal/on-demand or institutional mirror
procedural history -> matter-local append-only graph
external public authority discovery -> federated
```

The proof graph remains:

```text
Orders
x MaterialFacts
x LegalPropositions
x Evidence
x SourceAnchors
x Conflicts
x Residuals
```

but storage policy decides where each underlying byte object lives.

This is important for self-represented/AI-authored material: the visible formulation, reconstructed intended issue, original source text, legal authority, and court response remain distinct graph coordinates even if not all are retained as local text indefinitely.

## Medical/clinical deployment

Patient bytes default to the protected clinical system or an explicitly admitted local/institutional store. Public medical/science ontologies and guideline discovery may be remote.

Source-role distinctions remain mandatory:

```text
patient report
clinician observation
measurement/lab
model inference
external guideline/evidence
```

Remote capability never implies disclosure permission.

## Parallel public ontologies

The skeletal graph may carry candidate links to multiple public ontologies:

```text
Wikidata
DBpedia
medical/science ontologies
OEIS
jurisdiction/domain-specific legal vocabularies
```

Parallel candidates remain parallel:

```text
ontology candidate
!= ontology transplant
!= claim truth
```

A local skeleton can therefore be small while still carrying enough identity anchors to query several external semantic systems on demand.

## StatiBaker / Casey / ZOS placement

Reuse the existing ownership boundaries:

```text
Casey -> live candidate/workspace/collapse/build state
StatiBaker -> append-only observer/operation/build receipts and references
SensibLaw/SL -> truth construction, admissibility and promotion
ZOS -> non-authoritative semantic overlay/hypothesis/object identity layer
```

Storage/federation must not transfer authority between these components.

A content-addressed object can be mirrored by many peers while Casey still owns its candidate/workspace semantics and StatiBaker records only bounded refs/digests/receipts.

## High-alpha work to complete now

1. Typed skeletal-corpus identity/availability model.
2. Query-indexed skeleton adequacy witnesses using existing `FactorsThrough` machinery.
3. Append-only retention-transition receipts.
4. Cross-machine capability discovery + admitted typed-job transport over existing distributed worker/ZOS machinery.
5. One end-to-end legal specimen (Mabo remains the flagship) demonstrating:

```text
argument
-> literal propositions
-> authority/application coordinates
-> support + defeaters + comparators
-> residual
-> selective/full-source reacquisition
-> review/payment
-> explanation
```

## Defer until receipts justify it

- bespoke corpus compression codecs;
- universal local mirrors;
- global replication optimisation;
- on-chain storage as a default;
- sophisticated ZKP storage before a concrete disclosure problem exists;
- broad Nat-scale mirroring before smaller workloads show what deserves caching/replication.

## Measurements to collect

```text
hot bytes
cold bytes
reference-only object count
dedup ratio
re-fetch/cache-hit rate
reacquisition latency
parse cost/source
residual contraction/acquired byte
residual contraction/network request
source unavailability rate
skeleton adequacy failures by consumer
replication cost vs avoided reacquisition cost
```

Compression/retention optimisation should follow these receipts rather than precede them.

## Roadmap summary

The practical target is:

```text
private/local corpus as required
+ append-only evidence/history
+ consumer-adequate skeletal graph
+ selected caches/replicas
+ federated reacquisition and compute
```

not:

```text
every participant maintains a complete corpus mirror
```

The governing equations are:

```text
self-populating != self-hoarding
world representability != local materialisation
local possession != consumer adequacy
replication != authority
```

This storage/materialisation tranche runs in parallel with, not ahead of, the next federation seam: cross-machine capability discovery and admitted job transport.