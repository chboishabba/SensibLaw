# Legal IR system-level review

This note extends the existing Legal IR federation plan.

Legal review is not limited to atomic coordinates such as actor, prohibition,
exception attachment, holding, commencement date, or jurisdiction. Reviewers must
also be able to assess whether SensibLaw/ITIR:

- identified the correct law or legal aspect;
- placed it correctly in the graph;
- assigned the correct structural role and legal function;
- represented the correct legal outcome;
- derived a defensible implication;
- joined sources coherently;
- produced a subgraph fit for its stated use.

`src/pnf/legal_system_review.py` models these as typed `LegalReviewClaim` objects.
Claim kinds include identification, graph placement, structural role, legal
function, legal outcome, legal implication, cross-source join, temporal validity,
jurisdictional scope, reconstruction fitness, subgraph coherence, and build
fitness.

A `LegalSystemReviewAttestation` records a review state for each claim:
`supported`, `supported_with_residuals`, `unsupported`, `contested`, `unresolved`,
or `not_reviewed`. The overall act may endorse, approve with residuals, reject,
contest, abstain, or supersede.

System-level review does not mutate PNF or graph revisions. Projections remain
credential- and institution-scoped, preserve disagreement, and never close truth.

The transport boundary remains separate. `src/pnf/legal_artifact_transport.py`
exports immutable SensibLaw artifacts using the ZOS identity tuple:

```text
(kind, object_id, content_digest, producer_contract, producer_locator_set)
```

A successful fetch or digest check records availability only. It does not promote
PNF, accept Legal IR, import trust, or adopt remote review state.

The current full-parser probe still identifies four generic PNF composition gaps:
modality, condition, exception, and temporal validity. These remain compiler work;
they must not be filled by a second legal parser or by copying legacy extractor
conclusions into PNF.
