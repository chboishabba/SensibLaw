# Federated Legal IR stack synthesis

## Purpose

This note records the architecture after merged PRs #442 and #443, the first full-model legal-PNF probe, and review of the relevant `meta-introspector` repositories.

The systems must remain separate and joined by immutable artifact contracts.

## Four-layer stack

```text
1. SensibLaw semantic authority
   source artifact
   -> one media adapter
   -> one canonical text substrate
   -> one parser spine
   -> PNF
   -> Legal IR
   -> lawyer/institution review and local promotion

2. Legal Semantic Build
   immutable package linking:
   - refined PNF graph
   - Legal IR projection
   - legacy diagnostic witnesses
   - semantic comparison ledger
   - PNF coverage demands
   - optional federation bundle

3. eRDFa / Kant publication
   - canonical artifact bytes
   - CBOR shards and manifests
   - CIDs and SHA-256 witnesses
   - publication and retrieval metadata
   - renderer-independent product views

4. ZOS convergence
   - inventory announcement
   - missing-object reconciliation
   - replay locators
   - fetch and digest verification
   - artifact/receipt availability convergence
```

Ownership is strict:

```text
SensibLaw decides meaning, review state, trust scope, and promotion.
eRDFa/Kant packages, publishes, addresses, and renders immutable artifacts.
ZOS determines whether peers possess identical bytes and recovers missing objects.
```

Publication or replication never grants semantic authority.

## Empirical checkpoint

The first full parser-model legal probe produced:

```text
236 PNF factors
0 Legal IR observations
6 legacy witnesses
9 comparison rows
4 PNF coverage demands
0 Wikidata lookup demands
0 identity closures
flattened_union = false
```

Actor, conduct, and object are present in PNF. The confirmed missing generic compositions are:

```text
modality
condition
exception
temporal validity
```

This is not a Legal IR failure. Legal IR correctly refused to invent legal semantics that generic PNF had not reconstructed.

The repair path is:

```text
legacy witness
-> comparison ledger
-> PNF coverage demand
-> generic parser-observation composition
-> rebuilt PNF
-> regenerated Legal IR and ledger
```

Legacy output must never write directly into PNF or Legal IR.

## Product definition

Legal IR is a federated, source-grounded, semantically typed legal knowledge product.

A useful analogy is:

```text
Wikipedia
+ immutable typed graph revisions
+ exact source-span anchoring
+ explicit jurisdiction and legal time
+ retained disagreement
+ professional review attribution
+ institution-scoped trust projections
+ reconstruction and publication receipts
```

Reviewers act on exact graph revisions or coordinates, not an undifferentiated AI answer. Review acts include:

```text
endorse
approve_with_residuals
reject
contest
abstain
supersede
```

Different institutions may publish scoped views such as:

```text
endorsed by admitted Queensland barristers
accepted by this firm's administrative-law team
contested by constitutional specialists
unreviewed by this institution
superseded after amendment or appeal
```

No review tally closes legal truth.

## Legal Semantic Build authority

| Surface | Role | Authority |
|---|---|---|
| refined PNF graph | candidate semantic state | candidate semantic authority |
| Legal IR projection | operational legal view | deterministic projection only |
| legacy witnesses | independent extractor observations | diagnostic only |
| comparison ledger | alignment and disagreement | audit only |
| PNF coverage demands | reconstruction work queue | planning only |
| federation bundle | revisions, credentials, attestations, views | governance evidence |

The invariant is:

```text
Legal IR = Project(refined PNF)
```

not a union of PNF, Legal IR, legacy output, and remote state.

## External repository roles

### `zos-server`

ZOS is the convergence layer. Its canonical identity shape is compatible with SensibLaw:

```text
(kind, object_id, content_digest, producer_contract, producer_locator_set)
```

It should inventory, reconcile, fetch, and digest-verify immutable SensibLaw artifacts. It must not decide legal truth, trust, graph promotion, or semantic merge.

Peerable SensibLaw objects include:

```text
LegalSemanticBuild
LegalIRProjection
FederationBundle
ReviewAttestationBundle
PublicationReceipt
VerificationReceipt
```

### `erdfa-publish-rs`

This is a publication substrate for content-addressed CBOR shards, manifests, CIDs, typed presentation components, and progressive product views.

Useful views include Legal IR pages, provision maps, holding trees, review ledgers, amendment timelines, trust projections, and source-span browsers.

Its component and arrow types are publication semantics, not PNF or Legal IR semantics.

### `kant-zk-pastebin`

Kant is a publication/storage endpoint with content addressing, CIDs, SHA-256 witnesses, and eRDFa/RDFa metadata. It is not a legal semantic authority.

### Other repositories

`erdfa-py` may provide deterministic envelope/hash helpers. `mesh-sync-rs` is compatibility transport, not the canonical Legal IR sync path. Small ZOS plugin repositories are extension points until their contracts mature. Proof systems may produce verification receipts but do not acquire legal-review authority.

## Strategic outcome

```text
SensibLaw alone:
  typed, source-grounded, reviewable legal knowledge product

SensibLaw + eRDFa/Kant:
  publishable content-addressed legal commons

SensibLaw + ZOS:
  peer-replicated digest-verified legal artifact network

Combined:
  federated legal knowledge infrastructure where meaning is reconstructed,
  provenance is exact, lawyers review graph coordinates, institutions expose
  scoped trust views, disagreement remains first-class, and immutable artifacts
  replicate without central semantic control.
```

The current bottleneck is semantic production density, not federation design. Generic PNF must now reconstruct modality, condition, exception, and temporal-validity structures so Legal IR has substantive graph content for lawyers to review and peers to replicate.
