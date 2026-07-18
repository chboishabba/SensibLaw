# PostgreSQL semantic compiler P0

Date: 2026-07-18
Status: active implementation contract

## Purpose

The PostgreSQL compiler is the durable operational projection of the shared
semantic compiler. It must persist semantic structure, not merely a
mention-identity inventory.

```text
canonical document
-> one shared annotation graph
-> declared generic reductions
-> predicate / argument / eventuality / time / place / quantity / attribution factors
-> sparse document-local typed meets
-> immutable factor revisions
-> precise unresolved external demands
```

This remains corpus-neutral. GWB and AU are proof fixtures only; neither can
add a grammar, factor kind, or database table specific to its corpus.

## Generic reduction contract

Reductions consume immutable annotation layers and declared relation algebra.
They may emit branch-preserving candidates for nominal structures, predicates,
arguments, eventualities, temporal and spatial expressions, quantities,
references/attribution, coordination, and embedded propositions. They may not
select an external identity, assert a proposition, or promote a claim.

Date-shaped and event-reference branches remain distinct. A discourse relation
may license an event-reference alternative beside a literal date alternative;
it cannot decide which event occurrence is meant.

## Current local-typing quality tranche

The first proper HTML baseline showed that form-only local typing leaves too
many meaningful spans as generic mention identities. Before adding EPUB/PDF
adapters or any external snapshot backend, the compiler must project existing
public annotation and relation structure into local type hypotheses.

The projection is declarative and branch-preserving. Predicate heads, argument
roles, temporal anchors, spatial anchors, modified nominals, coordination, and
embedded propositions may each contribute a locally typed alternative with its
annotation/relation provenance. They do not select an entity, decide that an
event occurrence is meant, or collapse compatible alternatives. A locally
typed role is still distinct from an externally resolved person, institution,
place, or event.

The acceptance measure is not a particular corpus count. On the same input and
compiler declarations, the new projection must be deterministic; it must
reduce generic `local_type_unresolved` pressure where public structure exists;
and it must retain an explicit residual wherever external identity or a
semantic distinction remains open.

Adding this declaration changes the semantic compiler contract revision. It
invalidates semantic build descendants and demand projections, while preserving
the content-addressed canonical document and annotation inputs.

## Structural-semantics expansion tranche

The next local-only expansion is guided by a diagnostic partition, not by a
target reduction in one residual counter. Every remaining `local_type_unresolved`
mention must be classified from observations already available in the public
annotation graph: nominal head or modifier, predicative structure, syntactic
argument role, temporal/spatial shape, coordination, clause/composition,
quantity/reference shape, missing annotation, boundary failure, or genuinely
weak semantic content. The report ranks `annotation shape × missing generic
reduction × PNF impact`; it does not select identities or reinterpret source.

Each reducer is an immutable declaration over annotation and relation types.
It emits typed alternatives, graph constraints, residual rules, and a
provenance-bearing application receipt. It must be branch-preserving:

```text
annotation observations
-> declared reduction application
-> alternatives + factor/constraint/relation edges + residuals
```

The first declarations cover nominal descriptions, predication/eventuality,
syntactic argument relations, and clause/composition boundaries. Nominal
descriptions distinguish instance/class/role/property/kind/event/nonreferential
possibilities without identifying a referent. Predication keeps syntactic
arguments separate from semantic-role alternatives and keeps reporting
eventualities distinct from their proposition content. A local reduction may
close only the residual it justifies; referent identity, role-time scope,
truth, event occurrence, attachment, and external identity remain explicit
when unsupported.

Temporal, spatial, coordination, measurement, reference, attribution, and
modifier-scope declarations follow through the same carrier once the diagnostic
shows the parser exposes the needed observations. Date forms remain distinct
from possible event references, and coordination is never silently distributed.
This tranche remains local-only: no EPUB/PDF admission, external retrieval,
identity resolution, claim promotion, corpus-specific declaration, or hidden
lexical catalog is permitted.

### Constraint-emission implementation slice

The first implementation target is the high-impact syntactic-argument
partition. Relation declarations must emit explicit constraint rows with
source/target factor references, rather than only a coarse relation-observation
factor. Syntactic subject/object/oblique/complement edges remain distinct from
semantic-role alternatives. Nominal head/modifier edges and reporting-event /
proposition-content edges follow the same declaration-owned carrier.

The diagnostic `parser_annotation_missing` bucket must be subdivided into
actionable alignment, boundary, unprojected-relation, markup/function-fragment,
and semantically-weak causes. Refinement receipts must show which residuals
were closed, retained, or opened; external identity, event occurrence,
attachment, and truth remain open unless a later evidence layer justifies them.
This constraint-emission schema is compiler contract
`postgres-semantic-compiler:v0_4`.

### Lossless parser-observation slice

The next implementation boundary is not another extractor.  The public parser
already exposes token offsets, sentence membership, POS, lemma, morphology,
dependency labels, and dependency heads.  The compiler must preserve those
observations in one immutable `AnnotationGraph` and record the parser model and
capabilities that produced them.  The relational bundle becomes a deterministic
projection of that graph; it must not parse the text a second time.

Predicate observation is structural rather than direct-object-centred.  A
parser-supported predicate remains observable with zero or many arguments,
including intransitives, copular/state predicates, passive predicates,
clausal complements, auxiliaries, negation, modality, obliques, and predicate
modifiers.  These remain syntactic observations.  They do not establish an
agent, patient, referent, event occurrence, or proposition truth.

PNF reductions consume the preserved observations to emit generic predicate,
eventuality/state, argument/reference, tense/aspect/voice/modality/polarity,
and clause/proposition factors and constraints.  A pronominal grammatical
argument becomes an unresolved PNF argument/reference branch constrained by
parser observations; it is never classified by a hidden English word list.
Reporting eventualities and their proposition content remain distinct.

Parser-supported closed and open clausal complements are reduced through the
generic composition carrier: a host predicate and embedded predicate are
linked by a structural `content_of` constraint.  This is not a reporting-verb
catalogue and does not assert that the embedded proposition is true; its
truth-status residual remains open.

The untyped diagnostic is valid only when it can account for the full seam:

```text
parser capability -> observed annotation -> graph projection
-> applicable declaration -> consumed reduction -> PNF output
```

It must therefore report capability absence, observation absence, projection
loss, span/token alignment conflict, declaration absence, application failure,
incomplete PNF constraint, remaining binding/refinement work, or genuinely
weak structure.  Historic `markup_fragment` totals derived from missing
diagnostic input are invalid baseline metrics and must not be used for
planning.

This lossless-observation change advances the compiler contract to
`postgres-semantic-compiler:v0_5`: it invalidates annotation descendants and
semantic builds, while preserving canonical text and source-normalisation
artifacts.

Implemented in the first v0.5 slice: the public spaCy adapter receipts its
model and capabilities; `compile_document` shares that parse with mention
licensing and the relational projection; parser token/span/dependency/capability
observations are persisted in the annotation graph; and subject-only,
oblique, complement, and inflection observations can reach generic PNF
factors.  This establishes the evidence seam.  It does not yet perform
antecedent binding, semantic-role selection, reporting-content truth
evaluation, or external reconciliation.

### Local binding and role-refinement slice

The next v0.5 implementation consumes the richer local graph before any
registry request.  It produces bounded, document-scoped **candidate** binding
and role assessments; neither assessment resolves identity, occurrence, or
truth.

For an unresolved PNF reference argument, the compiler may consider only
structurally accessible factors in the same document.  Candidate generation
uses parser-observed sentence/clause position, morphology, syntactic binding
relations, and the candidate's PNF factor kind.  It emits explicit relations
such as `possible_coreference_with`, `possible_eventuality_reference`,
`possible_proposition_reference`, and `binding_incompatible_with`.  A
candidate is a branch in the reference factor, never an equality assertion.
An expletive-compatible grammatical subject retains its expletive branch and
does not create an entity-resolution obligation merely to fill syntax.

Semantic-role work is likewise a typed local meet, not a verb lexicon.  The
compiler records that a syntactic subject/object/oblique constraint is
satisfied by the observed parse, then uses voice, morphology, predicate
structure, and declared predicate-class alternatives only to retain or reject
role *alternatives*.  In particular, a passive syntactic subject never gains
an automatic agent interpretation.

Constraint evaluation is a separate immutable assessment with one of:

```text
not_evaluated | satisfied | satisfied_with_alternatives
| contradicted | insufficient_evidence
```

It can close only its declared structural residual.  Factor refinements record
the prior and resulting factor, added/retained/rejected alternatives,
residual transitions, evidence/meet references, and leave unrelated factors
unchanged.  Resolution-demand projection consumes the resulting revision, so
it asks for an antecedent or role-specific evidence only when local structure
has not already discharged that obligation.

This refinement change advances the compiler contract to
`postgres-semantic-compiler:v0_6`, invalidating local meet, refinement, and
demand descendants while retaining source normalisation and parser-observation
artifacts.

Implemented in the first v0.6 slice: auxiliary-attached subjects are retained
by the public relational projection; local PNF constraints receive immutable
assessments; pronominal factors receive bounded document-local candidate
branches; and role refinements preserve patient/theme rather than agent for a
parser-marked passive subject.  The generic local-type carrier now admits a
proposition family so parser-supported composition cannot fail merely because
an embedded content branch was observed.  GWB and AU compile through the same
declarations; no binding candidate closes identity.

## Development environment reproducibility

`uv.lock` is a repository artifact for the declared Python dependency graph.
It is retained and reviewed with dependency changes so local PostgreSQL,
future Nix shells, CI, and developer environments can converge on one locked
Python resolution. It is not a source receipt or semantic authority artifact.

## PostgreSQL contract

The compiler substrate supplements—not replaces—the established legal ontology.
Generic text, annotation, declaration, PNF, evidence, meet, refinement, and
build rows have no mandatory `legal_source`, `actor`, or `event` foreign key.
Those legal rows may later link to compiler outputs through explicit bridges.

Declarations are immutable, revisioned rows:

```text
grammar declaration
type declaration
relation algebra declaration
closure contract
authority policy
```

Every build records exact declaration revisions consumed. Build keys form a
dependency chain for canonicalisation, tokenisation, annotation, reduction,
PNF construction, local meet planning, typed meets, factor refinement, and
demand projection. Reuse is valid only for an identical key and dependency
set; a changed grammar invalidates reductions and descendants, not unchanged
canonical text or tokenisation.

The authoritative tables retain normalised, queryable factor and relation
structure. Immutable backend payloads and receipts may use JSONB, but JSON is
not the sole representation of PNF semantics.

## Local refinement and demands

Local evidence can genuinely revise a factor revision while preserving its
stable factor identity. A refinement receipt records prior/result revisions,
added/retained/rejected alternatives, residual transitions, evidence, and an
unchanged-factor witness. It may close a local role/type obligation, but it
must leave external identity open when no registry evidence exists.

Only refined, still-open factors produce `ResolutionDemand` rows. A demand
includes its factor revision, resolution subject/formal role, type alternatives,
requested facets, typed time/place constraints, document scope, pressure, and
budget. It is a plan, never an identity decision or network execution.

## P0 acceptance

`gwb-mini` and the AU fixture must compile through the same declarations and
engine. The proofs must show structured PNF factors, sparse local meet plans,
immutable non-no-op refinements where local evidence warrants them, and
precise unresolved demands. They must not make a string match close identity,
conflate dates with events, or add corpus-specific reducer code.

External snapshots, cross-registry event reconciliation, readiness, live
scheduling, codec/posting optimisation, legacy SQLite retirement, and
DuckDB/Parquet analytics are later tranches.

## First non-fixture corpus run

The first proper corpus baseline is the existing raw GWB public-bios HTML
collection. HTML support belongs in the generic media-adapter boundary and
must use a structural HTML parser; it may not introduce a GWB adapter or a
regex tag stripper. The run is local-only and records source-normalisation
receipts, factor/residual distributions, sparse-meet rates, demand counts, and
build reuse. EPUB/PDF books remain a later capability-specific ingestion
tranche.
