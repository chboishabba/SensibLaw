# Legal IR as a federated SensibLaw product

## Product thesis

Legal IR is not merely an internal compiler artifact. It is a public, reviewable,
versioned legal knowledge product: a semantically typed and logically constrained
commons whose graph revisions remain linked to exact legal source spans, PNF
builds, jurisdictions, legal time, and attributable professional review.

A useful analogy is Wikipedia's collaborative knowledge surface, but the Legal IR
product differs in four decisive ways:

1. contributions are typed graph revisions rather than prose-page edits;
2. every legal assertion is source- and span-grounded;
3. disagreement is represented explicitly rather than erased by a current page;
4. trust is projected from attributable reviewer and institution scopes rather
   than inferred from anonymous popularity.

The product boundary is therefore:

```text
legal sources
  -> canonical text
  -> one parser spine
  -> refined PNF
  -> Legal IR graph revisions
  -> lawyer/institution attestations
  -> scoped trust projections
  -> public, restricted, or institutional views
```

## Semantic build boundary

The following artifacts are packaged in one `LegalSemanticBuild` but never
flattened into a single authority plane:

| Surface | Role | Authority |
|---|---|---|
| refined PNF graph | candidate semantic state | semantic candidate authority |
| Legal IR | deterministic PNF projection | projection only |
| legacy observations | independent extractor witness | diagnostic only |
| comparison ledger | alignment, gaps, disagreement | audit only |

Legal IR is always rebuildable from the refined PNF graph. Legacy witnesses may
create `PNFCoverageDemand` objects, but may not create or mutate PNF factors.

## Federated graph object

A publishable contribution is an immutable `LegalGraphRevision`:

```text
revision_ref
subject_ref
payload_hash
prior_revision_refs
source_span_refs
legal_system_refs
jurisdiction_refs
temporal_refs
author_ref
institution_ref
build_ref
revision_state
```

The payload may represent a norm, element, exception, burden, holding, treatment
relation, transition, WrongType link, remedy relation, or another typed Legal IR
object. A revision does not overwrite its predecessor.

## Professional review acts

A lawyer or institution reviews an exact graph revision by creating a
`LegalReviewAttestation` with one of:

```text
endorse
approve_with_residuals
reject
contest
abstain
supersede
```

Attestations are coordinate-sensitive. A reviewer may endorse the extracted
holding while leaving precedential scope unresolved, or approve a prohibition
while contesting its temporal validity.

```text
review_state = approve_with_residuals
coordinate_states:
  predicate = satisfied
  actor = satisfied
  jurisdiction = satisfied
  legal_time = unresolved
  exception = contested
```

The attestation records reviewer identity, credential evidence, institution,
reasons, source evidence, creation time, optional signature, and superseded
attestations.

## Credentials do not confer truth

`ReviewerCredential` records evidence such as admission, practice area,
institution, jurisdiction, and validity interval. It permits consumers to define
trust scopes. It does not grant universal truth authority.

Examples of scoped views:

```text
all reviewed Australian public-law claims
claims endorsed by this firm's administrative-law team
claims reviewed by admitted barristers in Queensland
claims accepted by a court-maintained federation
claims contested by at least two independent institutions
```

## Trust projections

A `FederatedClaimState` is a view over active attestations in a declared scope.
It can report:

```text
endorsed_in_scope
approved_with_residuals_in_scope
rejected_in_scope
contested
supersession_proposed
unreviewed_in_scope
```

No count or projection sets `truth_closed = true`. Competing endorsements and
rejections remain visible. Superseded attestations stop contributing to active
counts but remain immutable historical evidence.

## Federation model

Different operators may host compatible Legal IR shards:

```text
public SensibLaw federation
law-firm private federation
bar association review federation
university doctrinal federation
court or tribunal publication federation
community or Indigenous legal-system federation
```

Federation exchanges content-addressed graph revisions, credentials,
attestations, and receipts. Each receiver chooses its accepted credentials,
institutions, legal systems, jurisdictions, and promotion policies. A remote
endorsement is evidence of that review act, not a command to promote locally.

## Product views

The same underlying graph can support:

- source-first provision and judgment pages;
- visual element, exception, burden, and authority maps;
- cross-jurisdiction WrongType comparison;
- timelines of commencement, amendment, repeal, and judicial treatment;
- lawyer review queues and discrepancy surfaces;
- institution-specific trusted projections;
- public challenge and correction surfaces;
- machine-readable APIs for legal drafting, research, compliance, and oversight.

A typical consumer card should show:

```text
Prohibition candidate
  source span: section 4, chars 130-211
  PNF reconstruction: present
  Legal IR projection: present
  legacy witness: agrees
  reviewer state: 3 endorsements, 1 qualified approval
  contested coordinates: commencement, exception burden
  jurisdiction: Queensland
  legal time: unresolved
  promotion: candidate only
```

## Non-collapse laws

```text
review endorsement != legal truth
review majority != universal authority
credential != correctness
Legal IR projection != promoted law
court holding != globally true proposition
Wikidata candidate != resolved legal entity
legacy witness != PNF factor
remote federation state != local promotion
```

## Implementation sequence

1. Emit one `LegalSemanticBuild` manifest from the legal PNF probe.
2. Normalize legacy extractor rows into `LegacySemanticWitness` objects.
3. Generate signature-aware `SemanticComparisonRow` records.
4. Generate `PNFCoverageDemand` objects from legacy-only gaps.
5. Publish immutable `LegalGraphRevision` objects from approved Legal IR build
   coordinates.
6. Accept attributable `LegalReviewAttestation` objects.
7. Project scoped, non-authoritative `FederatedClaimState` views.
8. Persist and exchange federation bundles with idempotency and conflict receipts.
9. Integrate legally material Wikidata candidates as PNF refinement evidence,
   never as direct Legal IR writes.
10. Add public and restricted product surfaces over the same immutable graph.
