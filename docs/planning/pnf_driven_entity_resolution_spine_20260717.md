# PNF-Driven Entity Resolution Spine

Date: 2026-07-17
Status: canonical P0 architecture and implementation note

## Decision

The shared compiler spine begins before review-target selection. Its semantic
control loop is:

```text
canonical source text and anchored spans
-> shared language annotations and typed local world fragment
-> licensed mentions and eventuality candidates
-> cheap partial PNF
-> closure-pressure and coverage-pressure demands
-> registry-neutral resolution broker and cache-aware scheduler
-> bounded local/registry candidate evidence
-> cross-registry reconciliation and refined PNF alternatives
-> claim/target resolution
-> promote | audit | abstain | hold
```

PNF is therefore not merely a final representation produced after entity
resolution. It is a query planner, pruning surface, cache signature,
evaluation budget, residual inventory, and stopping criterion for deeper
resolution. It does not determine which meaningful entities and eventualities
exist in the candidate world model.

The loop is iterative. Local structure may create the first PNF skeleton;
candidate evidence may then refine its roles, boundaries, relations, and
identity assignments. No stage may rewrite canonical source text.

Two pressures operate concurrently:

- coverage pressure asks which meaningful spans, relations, quantities, roles,
  and eventualities remain weakly typed;
- closure pressure asks which unresolved obligations prevent a particular PNF
  from reaching its required closure depth.

Coverage controls admission to the candidate world model. Closure pressure,
expected downstream reuse, ambiguity reduction, evidence availability, and
estimated cost control evaluation order and depth. Residual-driven work is an
optimization strategy, not a license to ignore non-critical but typeable
content.

## Exhaustiveness contract

The intended recall boundary is broader than named-entity recognition:

- every token remains preserved and source-addressable;
- every logically meaningful span remains recoverable from the span lattice;
- ordinary nouns and phrases may generate instance, class, property, role,
  event-type, literal, or document-local candidates;
- stopwords normally contribute grammatical or relational evidence, but may
  participate in larger meaningful spans;
- every plausibly licensed external candidate is retained with its provenance
  and competing alternatives.

Logical exhaustiveness does not require eager materialization of every
contiguous span. The complete span space is defined over canonical boundaries,
while candidate records are instantiated lazily when licensed by an alias
index, structural grammar, local coreference, PNF demand, or explicit fallback
review. This preserves recoverability without making quadratic span storage the
runtime contract.

## Authority contract

These states are distinct:

```text
candidate identity != resolved identity != promoted fact
```

Ambiguous and unresolved identities are first-class assessment records, not
truth-bearing facts. A resolved identity may constrain a PNF role only under
the recorded resolution policy. A PNF or claim may acquire authority only at a
later explicit promotion boundary.

External registries are evidence backends. Wikidata is the first substantial
backend, not the owner of canonical token identity, local PNF, legal role, or
truth. The carrier must also admit legal/case registries, gazetteers,
document-local entities, WorldMonitor event/world-model snapshots, and other
revisionable identity sources.

Document-local coreference is allowed within a bounded, declared tranche.
Cross-context identity joins remain explicit, reviewable bridge proposals and
must not happen silently or by default. This preserves the anti-panopticon
boundary while allowing repeated mentions such as `George W. Bush`, `Bush`,
`the president`, and a locally licensed pronoun to share a candidate cluster.

## Shared carriers

The generic layer should own these receipt-free carriers:

### `MentionSpan`

- source and document references;
- canonical character interval and optional tokenizer-relative interval;
- canonical surface projection;
- local grammatical/structural evidence;
- surrounding-context references;
- generation reason and lattice state.

### `PartialPNF`

- predicate class and closure depth;
- typed unresolved and resolved slots;
- local span references;
- structural, temporal, relation, and type constraints;
- residuals that explain what remains unresolved.

### `ResolutionDemand`

- PNF slot and mention references;
- expected role and candidate kinds/types;
- relevant temporal and relation constraints;
- evaluation budget;
- allowed next expansion.
- requested evidence facets, closure impact, coverage impact, expected reuse,
  cost bound, and deadline class.

### `EntityCandidateSet`

- document-local and external candidate references;
- lexical, structural, temporal, type, hierarchy, and PNF compatibility
  evidence;
- competing candidates and deterministic ranking;
- registry snapshot and provenance references;
- candidate-only authority state.

### `CoreferenceCluster`

- member mention references;
- cluster-local aliases and recurrence evidence;
- candidate-set reference;
- context boundary and non-global scope.

### `ResolutionAssessment`

- `resolved | ambiguous | rejected | abstained` disposition;
- selected and rejected candidates with reasons;
- evidence and policy versions;
- unresolved reasons and next permitted expansion;
- no promotion authority.

### `PNFRefinement`

- prior PNF reference;
- resolution-assessment references;
- refined slot assignments;
- factorized alternatives;
- remaining residuals and closure depth.

Candidate alternatives should remain factorized over one local PNF skeleton
until review, contradiction analysis, or interacting constraints require full
alternative materialization.

### Event and external-identity carriers

Event handling must reuse the shared language annotation and reducer layer; it
must not introduce a parallel parser or a fixed list of trigger words.

`EventualityCandidate` carries source/predicate spans, argument bindings,
eventuality-class alternatives, aspect/modality/polarity, temporal candidates,
and residuals. It distinguishes linguistic eventuality, locally typed event,
event occurrence, and externally reconciled event identity. Event classes and
event occurrences remain separate: an attack may be typed confidently before
the particular occurrence is known.

`EventObservation` preserves what one source asserted or measured, including
observation/report/update time, source lineage, location/participants,
measurements, and provenance. An observation, forecast, alert, rolling state,
report, or cluster must not be coerced into an event occurrence. Relations such
as `observation_of`, `forecast_of`, `state_of`, `report_of`, and `cluster_of`
remain explicit.

`ExternalIdentityCandidate` is registry-neutral and records registry,
external identifier, pinned snapshot reference, identity layer, type
candidates, temporal/spatial extent, participants, aliases, and provenance.
Cross-registry relations may include `same_as`, `possible_same_as`,
`observation_of`, `member_of_event_cluster`, `instance_of_event_type`,
`derived_from`, `supersedes`, and `conflicts_with`. These relations do not grant
authority.

## Registry-neutral scheduling

The parser and PNF carriers remain backend-blind. They emit typed evidence
demands, never Wikidata requests, SPARQL queries, or WorldMonitor calls. A
resolution broker selects local evidence, cached registry snapshots, or an
allowed external backend.

Network work is interspersed with local annotation, typing, coreference, and
PNF refinement, while backend adapters may coalesce compatible work into
bounded microbatches. The scheduler must:

1. satisfy demands from local state or pinned cache where possible;
2. deduplicate identical and overlapping demands across mentions/documents;
3. coalesce concurrent cache misses and form backend-specific microbatches;
4. obey backend-specific rate limits with token/leaky buckets, bounded jittered
   retry, and negative caching;
5. prioritize demands by closure impact, coverage impact, downstream reuse,
   ambiguity reduction, evidence availability, and cost;
6. continue useful local work while network evidence is pending;
7. feed returned evidence into only the affected factors and cancel obsolete
   work;
8. retain snapshot/version, freshness, cache, fetch, and provenance evidence.

This gives an interspersed compiler view without degenerating into one HTTP
request per mention or one corpus-wide blocking batch.

## Event reconciliation as a typed meet

Cross-registry event resolution asks whether two partial event descriptions
admit a coherent shared occurrence, not whether their labels produce a high
scalar similarity score. `EventMeetAssessment` compares typed coordinates:

- temporal roles and extents: occurred, began, ended, observed, reported,
  updated, or forecast;
- spatial roles and relations: origin, epicentre, observation point, affected
  area, jurisdiction, route/track, containment, or intersection;
- role-preserving participant bindings and partial participant sets;
- event-type lattice compatibility and related-but-distinct eventualities;
- mention/alias evidence, which remains weak mention-to-event evidence;
- provenance lineage: independent, derived, syndicated, aggregated, revised,
  superseding, or unknown;
- observation-to-occurrence morphisms.

Each coordinate yields `compatible`, `compatible_with_refinement`,
`unresolved`, `not_applicable`, `no_typed_meet`, or `contradiction`. Policy may
then derive `resolved_same_event`, `provisional_same_event`,
`related_distinct_events`, `insufficient_evidence`, or `contradiction`, while
retaining coordinate residuals. A scalar may order a review queue, but may not
replace typed promotion obligations.

## Parser and storage prerequisites

The entity-resolution substrate depends on a single stable coordinate system.
P0 therefore includes parser consolidation before the resolver becomes a
public runtime surface:

1. converge `src/section_parser.py` and
   `src/ingestion/section_parser.py` on one canonical implementation plus a
   compatibility import shim;
2. tokenize or annotate each canonical text once per declared tokenizer
   profile, then expose node and mention views by span;
3. retain one immutable canonical text/blob and make segments, units,
   provisions, mentions, candidates, coreference members, and PNF evidence
   refer to spans rather than storing authoritative text copies;
4. keep verbose text-bearing JSON as a compatibility/review projection;
5. key derived artifacts by source hash, canonicalization/parser/tokenizer
   versions, registry snapshot, and resolution/PNF policy versions.

The canonical character coordinate system remains authoritative. Token streams
are versioned views and must not silently become global semantic identity.
Downstream code must continue to use `sensiblaw.interfaces` parser and reducer
surfaces rather than raw regex or direct spaCy parsing.

### P0b.1 baseline licensing profile

The first runtime licensing profile is intentionally structural and
backend-free. Given canonical text plus source/document references, it must
use the public parser/reducer interfaces once to emit deterministic
`MentionSpan` records for:

- each non-structural lexical token, with a broad local type hypothesis;
- numeric literal tokens;
- maximal contiguous name-shaped token phrases;
- parser-annotated eventuality predicates where the active annotation profile
  supplies that evidence.

Structural/stopword tokens remain source-addressable and are recorded as
suppressed structural spans rather than discarded. The carrier records the
canonical token count and the complete contiguous-span cardinality, so an
unmaterialized phrase remains recoverable for later alias, grammar, PNF-demand,
or review expansion. This baseline does not use a dictionary, alias trie,
registry, bespoke event trigger list, coreference decision, identity ranking,
PNF mutation, or promotion.

The profile is not a claim that every materialized lexical span is an accepted
mention. A license only admits a span to later candidate generation and records
its expected candidate kinds and local structural typing.

Implementation status: P0b.1 now lives in
`src.policy.entity_resolution.build_mention_licensing_carrier`. It emits a
deterministic `sl.mention_licensing.v0_1` receipt with source-anchored
`MentionSpan`, `MentionLicense`, and `SuppressedSpan` projections. Alias/grammar
expansion and candidate retrieval remain later P0b work; document-local exact
surface recurrence is separately implemented below.

### P0b.2 document-local recurrence profile

Before aliases or candidate sets can be interpreted, repeated generated
mentions need a cheap, explicit local evidence surface. The recurrence profile
groups only mentions with the same case-folded, whitespace-normalized surface
inside the same declared document. It records the normalized surface and member
mention references, and materializes only groups with two or more members.

This is not coreference: it neither says that two surfaces have the same
identity nor treats distinct surfaces such as `Bush` and `the president` as
aliases. It does not construct candidates, select a registry, mutate PNF, or
promote a fact. Alias/grammar/PNF-demand expansion may later consume these
groups as document-local recurrence evidence, with any cross-surface relation
remaining separately assessed and reviewable.

Implementation status: P0b.2 lives in
`src.policy.entity_resolution.build_mention_recurrence_carrier`. It emits a
deterministic `sl.mention_recurrence.v0_1` receipt under the same candidate-only
authority boundary. The profile is intentionally backend-free and prohibits
cross-document groups.

### P0b.3 bounded expansion requests

Alias, grammar, and eventual PNF-demand work must be able to widen the lazy
lattice without treating a widened phrase as an identity decision. A caller may
therefore submit an explicit, source-anchored request for a non-empty canonical
token interval with one of three reasons: `alias_hint`, `grammar_phrase`, or
`pnf_demand`. The request must name its source/document, expected candidate
kinds, and supporting context references. The expansion carrier verifies the
canonical-text digest and token bounds, deterministically reuses an existing
licensed span when the interval is already materialized, and otherwise emits a
new `MentionSpan` plus candidate-only `MentionLicense`.

The request reason records why further candidate generation is justified; it is
not evidence that an alias is correct, that a grammar interpretation is true,
or that a PNF slot has been resolved. This profile has no dictionary, alias
trie, registry lookup, candidate set, coreference decision, PNF mutation, or
promotion effect. An actual PNF producer remains P0c work. Bounded candidate
retrieval over caller-supplied evidence remains a separate P0b stage.

Implementation status: P0b.3 lives in
`src.policy.entity_resolution.build_mention_expansion_carrier`. It emits a
deterministic `sl.mention_expansion.v0_1` candidate-only receipt, including
the submitted requests, created spans, reused spans, and licenses. It checks
source/document identity, canonical-text hash, token cardinality, token bounds,
and context references before any expansion is emitted.

### P0b.4 alias-index request production

An alias index may contribute lexical *hints*, but it must remain separate
from a registry, identity decision, and candidate set. A caller supplies an
explicit, provenance-bearing alias entry as a normalized canonical-token
sequence together with expected candidate kinds, local type hypotheses, and
context references. The generic producer finds exact contiguous token matches
in one canonical text and emits deterministic `alias_hint`
`MentionExpansionRequest` records for the bounded expansion carrier.

The entry does not carry a selected external identifier, ranking, or assertion
that a matched surface denotes the same thing in every context. In particular,
an entry for the token sequence `9 / 11` may request a source span but cannot
silently become `911`, an emergency number, or an event identity. The caller's
index provenance stays attached as context; later candidate retrieval and PNF
constraints decide what, if anything, is compatible with the mention.

Implementation status: P0b.4 lives in
`src.policy.entity_resolution.build_alias_expansion_requests`. It is
backend-free and produces only request records plus an exact-match receipt. It
does not materialize mentions itself, query an index or registry, construct
candidates, perform coreference, alter PNF, resolve identity, or promote a
claim. Structural-grammar request production is separately implemented below;
bounded candidate retrieval remains a distinct later stage.

### P0b.5 structural-grammar request production

The first structural-grammar adapter consumes the public canonical parser and
token-span interfaces, never a raw parser or external backend. Its initial
generic profile emits maximal locally annotated nominal phrases: contiguous
determiner, adjective, numeral, common-noun, or proper-noun tokens containing
at least one noun/proper-noun head. It preserves the parser's token boundaries
and records the profile/context used to derive each `grammar_phrase` request.

This is syntactic admission, not a conclusion that the phrase denotes an
entity, role, relation, class, or event. The emitted expected candidate kinds
are deliberately broad local type hypotheses. A phrase can later be reused or
rejected by the bounded expansion carrier; the profile does not resolve an
identity, infer a PNF role, create a candidate set, or replace the shared
eventuality reducer. Missing or incompatible parser annotation emits no
structural request rather than inventing a phrase boundary.

Implementation status: P0b.5 lives in
`src.policy.entity_resolution.build_grammar_expansion_requests`. It is
backend-free and emits deterministic `grammar_phrase` request records only.
Bounded candidate retrieval remains the next P0b stage.

### P0b.6 bounded candidate retrieval

Candidate retrieval must not make parsers registry-aware or turn a lexical
match into an identity decision. The first bounded profile therefore accepts
only caller-supplied, provenance-bearing catalog entries and already anchored
mentions. It compares canonical tokenizer token sequences exactly and emits an
`EntityCandidateSet` for every input mention: zero alternatives is an explicit
result, while several equally matching entries remain several alternatives.

Catalog evidence may identify a local or external candidate and cite a pinned
snapshot, but it is never a selected identity. The retrieval profile performs
no network request, ranking, type inference, coreference decision, PNF change,
or promotion. In particular, its token-sequence comparison preserves the
distinction between `9 / 11` and `911`; contextual/PFN work must decide which
candidate, if any, is compatible later.

The catalog is bounded by its caller and stays independently reviewable through
entry, evidence, and optional snapshot references. A future scheduler may
refresh or microbatch backend evidence, but that belongs to the registry-neutral
P0c broker rather than this offline matcher.

Implementation status: P0b.6 lives in
`src.policy.entity_resolution.build_candidate_retrieval_carrier`, with
`CandidateCatalogEntry` as its bounded catalog input. It emits a deterministic
`sl.candidate_retrieval.v0_1` candidate-only carrier, exact-match receipts,
and one `EntityCandidateSet` per anchored input mention. Its deterministic
serialization key is an encoding invariant only: it is not a rank, preference,
or semantic interpretation, and consumers must treat alternatives as an
unordered set. Form derivation now precedes local semantic typing and coverage
pressure.

### P0b.7 form derivation and relation algebra

Lexical catalog matching cannot own semantic equivalence. Before a catalog may
be consulted, a source mention is represented as a set of typed form
alternatives and declared relations between them:

```text
surface form -> token sequence / numeric / date / abbreviation alternatives
             -> declared form relations -> later PNF compatibility
```

`FormCandidate` records a source-anchored linguistic form with its normalized
payload, derivation basis, and explicit ambiguity state. `FormRelation` records
only a declared relation between form candidates, such as
`orthographic_variant_of`, `numeric_rendering_of`, `spoken_form_of`,
`abbreviation_of`, or `component_of`. A declarative, caller-supplied lexical
profile may add language-specific form facts and compositional rules; it may
not name an external entity or select a candidate. Generic structural parsing
may emit integer, rational, and abbreviation alternatives, but it does not
turn a date-like form into an event.

Composition is branch-preserving: where more than one declared component path
is compatible with a rule, the carrier emits every bounded output alternative
and its component relations. It must never use insertion order, profile order,
or serialization order to choose a first linguistic derivation. Duplicate
derivations may be coalesced only when their source interval, output type,
normalized payload, and derivation basis are identical.

Thus `9 / 11` can retain rational and date-shaped alternatives, `911` can
retain an integer alternative, and `S11` can retain an abbreviation alternative
without any of them becoming a telephone number, legal provision, model, or
event. A later PNF may license a context-dependent relation such as
`metonymic_reference_to`; neither form derivation nor catalog ordering may do
so. Form candidates, form relations, entity candidates, resolved identities,
and promoted facts remain separate carriers.

Implementation status: P0b.7 lives in
`src.policy.entity_resolution.build_form_derivation_carrier`, with
`FormCandidate`, `FormRelation`, `FormLexiconEntry`, and
`FormCompositionRule` as its generic carriers. It is backend-free and
candidate-only.

### P0b.8 local typing and coverage pressure

The next carrier consumes anchored mentions, form alternatives, and public
parser/reducer annotations to emit local type alternatives. It does not choose
an external identity, infer an event occurrence, or close a PNF slot. A type
alternative must name its source form/span, semantic family (for example
entity, relation, quantity, role, eventuality, class, property, or literal),
declared local type, derivation basis, and ambiguity state. Profile rules may
add language facts and annotation-to-type reductions, but cannot name an
external identity, assert a registry relation, or promote a fact.

An independent coverage receipt reports each meaningful anchored item as
`typed`, `weakly_typed`, `untyped`, or `not_applicable`, with explicit reasons
and type-alternative references. It measures candidate-world coverage only;
it does not calculate PNF closure pressure, issue a resolution demand, or
interpret absence as a semantic contradiction. Thus every typeable entity,
relation, quantity, role, and linguistic eventuality can enter the local world
fragment while later PNF residuals decide which alternatives require deeper
evaluation.

Implementation target: shared, backend-free, candidate-only carriers in
`src.policy.entity_resolution`, using only the public parser/reducer interfaces
for annotation-derived evidence. Implementation status: P0b.8 now provides
`LocalTypeAlternative`, `LocalTypingRule`, `CoveragePressureAssessment`, and
`build_local_typing_carrier`. Built-in reductions remain structural (numeric
quantity, abbreviation form, calendar expression, and parser-annotated
linguistic eventuality); caller-profile rules provide other local types without
selecting an identity. The next P0 work is factorized `PartialPNF` construction
over this locally typed fragment.

### P0c.1 factorized PartialPNF and closure pressure

The first P0c carrier constructs a cheap, local `PartialPNF` skeleton from
declared generic slots and locally typed alternatives. A slot names a source
mention, expected semantic families, and one closure requirement:
`local_type` or `external_identity`. It retains matching local type references
as factorized slot alternatives; it must not materialize combinations across
subject, predicate, object, time, location, eventuality, qualifier, modality,
or polarity slots.

For each required slot, a separate closure receipt records exactly one state:

```text
locally_closed                 matching local type and local_type requirement
requires_external_resolution   matching local type but external identity needed
requires_local_typing          no compatible local type alternative
not_required                   an explicitly optional slot
```

This is an obligation inventory, not a resolution demand, candidate choice,
truth assertion, or promotion rule. It must remain independent of the P0b.8
coverage receipt: coverage asks whether meaningful source material has local
types; closure asks whether the declared PNF slot can reach its stated closure
target. The following P0c slice may turn `requires_external_resolution` and
`requires_local_typing` states into budgeted `ResolutionDemand` records.

Implementation status: P0c.1 now provides `PartialPNF`, `PartialPNFSlot`,
`PNFSlotAlternative`, `ClosurePressureAssessment`, and
`build_partial_pnf_carrier`. Skeletons are document-bounded, reference local
type alternatives rather than combining them, and expose no registry, demand,
resolution, or promotion effect.

### P0c.2 closure-derived resolution demands

`ResolutionDemand` is a registry-neutral request plan, not a request executor.
It may be derived only from P0c.1 `requires_external_resolution` or
`requires_local_typing` states. Each demand retains the PNF/slot/mention
anchor, expected semantic families, requested facets, budget class, and source
closure state. `requires_external_resolution` asks for identity and compatible
type evidence; `requires_local_typing` asks for bounded local typing evidence.
No demand is emitted for locally closed or optional slots.

Demand serialization is deterministic but non-prioritizing. A later scheduler
may order demands using budget, reuse, cache state, and backend conditions;
this carrier may neither choose a backend, issue I/O, choose an entity, nor
alter PNF closure. A `ResolutionDemand` is therefore an inspectable boundary
between PNF obligation and optional evidence acquisition.

Implementation status: P0c.2 now provides `ResolutionDemand` and
`build_resolution_demand_carrier`. It projects only unresolved P0c.1 slots
into source-anchored, facet-specific, budget-labelled demands.

### P0c.3 typed resolution subjects and event roles

Typed resolution subjects must precede scheduler design. Every unresolved
demand is attached to one explicitly declared subject kind:

```text
entity
event_type
event_occurrence
event_artifact
document_local_cluster
property_or_relation
```

An `event_occurrence` has formal role `occurrence`. An `event_artifact` must
declare one of `observation`, `cluster`, `forecast`, `report`, `alert`, or
`rolling_state`. Non-event subjects carry no event formal role. This prevents
an observation, cluster, forecast, report, alert, or state record from being
silently treated as the event occurrence it describes.

A resolution subject also carries its document-scoped target reference, PNF
slot role, expected local semantic families, compatible local type references,
and typed temporal, spatial, relation, and source-scope constraints. These are
candidate-world obligations only. Subject construction cannot infer an event
identity, reinterpret a registry record, choose a backend, or close PNF.

### P0c.4 semantic demand equivalence

Demand deduplication is permitted only when semantic requirements are equal.
The equivalence key includes:

```text
resolution subject kind and event formal role
document-scoped target reference
expected semantic families and local type alternatives
PNF slot role
temporal, spatial, relation, and source-scope constraints
requested evidence facets
document scope
```

Normalized surface text alone is never an equivalence key. Thus person/place/
institution readings of `Washington` remain separate, as do an earthquake
occurrence and an observation of it. Equivalent demands may be grouped under
one deterministic key with a receipt listing every member demand; grouping is
not resolution, prioritization, backend selection, or evidence retrieval.

Only after P0c.3 and P0c.4 are implemented may the registry-neutral cache and
microbatch scheduler contract be defined.

Implementation status: P0c.3/P0c.4 now provide `ResolutionConstraint`,
`ResolutionSubjectDeclaration`, and `build_resolution_subject_carrier`.
Every unresolved demand requires exactly one explicit typed declaration.
Occurrence/artifact role validation prevents role collapse, and semantic
equivalence groups retain all demand/subject members under a deterministic key.
The grouping receipt has no scheduling or deduplication execution effect. The
next slice is the append-only evidence-cache and microbatch scheduler contract.

P0c.5 is registry-neutral and side-effect-free. It consumes semantic
equivalence groups, matches typed demands to declared backend capabilities, and
emits explicit execution states for fresh/stale/negative cache hits, planned
fetches, unavailable or unsupported backends, and exhausted budgets. It does
not perform I/O, choose identities, rank candidates, reconcile event records,
or mutate PNF factors. A later document-local backend will prove the control
loop before external Wikidata/WorldMonitor adapters are introduced.

The scheduler is an execution carrier only. Cache entries remain immutable and
provenance-bearing; rate limits, batch limits, retry class, and stale acceptance
are planning metadata, not evidence of identity or truth.

## Coverage- and demand-driven control loop

The shared controller should:

1. obtain shared language annotations once through public parser/reducer
   interfaces;
2. license and locally type meaningful spans and eventualities into a candidate
   world fragment;
3. construct the cheapest locally supportable PNF skeleton;
4. calculate both coverage and closure pressure;
5. emit typed, budgeted, registry-neutral resolution demands;
6. attach typed entity/event resolution subjects and semantic equivalence keys;
7. retrieve exact/local/cached evidence before wider or costlier evidence;
8. schedule remaining external work through deduplicated backend microbatches;
9. reconcile entity/event candidates through typed obligations;
10. refine only affected factors of the PNF and candidate world fragment;
11. stop at the requested closure/coverage budget with explicit hold,
    ambiguity, abstention, or remaining weak typing;
12. widen only demands that justify further work.

A surface string alone is not a sufficient cache key. Candidate ranking for a
string such as `Washington` must vary with expected PNF role/type, predicate,
time, document context, and registry revision.

## Proving tranches

### GWB first

GWB is the first narrative-ambiguity proof. Its current public and broader
targeting inventories must be re-expressed as two independent problems:

- mention/entity ambiguity;
- claim/target ambiguity.

The GWB profile supplies source defaults, document-local alias hints, and
review labels only. It must not own entity-resolution or coreference methods.
The existing lane-specific `GWBTargetingCandidate` and `GWBTargetingResult`
surface in `src/policy/review_targeting_contract.py` is transitional and
overindexed. Its generic targeting semantics belong in the shared controller;
the remaining GWB wrapper should provide only fixture/profile mapping and
outward compatibility labels.

Acceptance fixtures should include repeated George W. Bush mentions, role
mentions such as `the president`, event aliases such as `9/11`, and competing
literal/entity readings. Ambiguity may collapse only through recorded evidence.

### AU second

AU reuses the same carriers for courts, statutes, agencies, parties, dates,
legal roles, decisions, and procedural events. Its stronger typed legal
structure should test whether PNF constraints improve resolution without
turning legal-source structure into a separate resolver.

### Nat/Wikidata backend

Nat supplies revision-pinned external entity snapshots, hierarchy evidence,
and receipts as one backend. It neither owns the shared resolver nor becomes a
mandatory dependency for GWB, AU, or arbitrary private/offline tranches.

### WorldMonitor backend

WorldMonitor is a resolvable external world-model surface, not merely a feed
and not an ontology authority. Its adapter should expose pinned/reproducible
snapshots containing record kind, aliases/title, event type, temporal and
spatial extent, participants, source observations, canonicalization metadata,
and provenance. A WorldMonitor record may denote an occurrence, observation,
cluster, rolling state, forecast, alert, or analytical signal; reconciliation
must preserve that role.

The integration maps WorldMonitor records into the same
`ExternalIdentityCandidate`, `EventObservation`, and event-meet carriers used
by other registries. Implementation must inspect the current sibling project
before fixing a concrete adapter schema; this note does not assume its present
runtime or API shape.

## P0 implementation sequence

1. Consolidate the section-parser substrate and span-only internal coordinate
   model while preserving compatibility projections.
2. Add lazy span licensing plus local semantic typing for meaningful entities,
   relations, quantities, roles, and eventualities using the public parser and
   reducer interfaces.
3. Add generic carrier validation and deterministic serialization for partial
   PNF, resolution demands, assessments, refinements, eventualities, external
   identities, observations, and event meets.
4. Add the bounded coverage/closure controller, residual-action registry,
   cache signatures, evaluation budgets, and stopping states.
5. Add the registry-neutral broker and cache-aware microbatch scheduler.
6. Add pinned Wikidata snapshots and then a schema-verified WorldMonitor
   snapshot adapter as independent backends.
7. Add cross-registry entity/event reconciliation and PNF refinement.
8. Extract generic targeting semantics from the transitional GWB-named
   contract and make targeting consume resolution/PNF alternatives.
9. Re-materialize the GWB ambiguity inventory with separate entity and target
   ambiguity counts and review receipts.
10. Adopt the same shared surface in AU; retain every external registry as an
    optional, revisioned evidence backend.

## Acceptance

- Every emitted mention, candidate, cluster, PNF slot, and claim target traces
  to canonical source spans.
- Candidate serialization, resolution reasons, cache signatures, and receipts
  are deterministic for fixed inputs and versions. Serialization order is not
  a candidate ranking, preference, or semantic relation.
- One, many, or zero candidates survive explicitly; no ambiguity is silently
  collapsed.
- Ordinary nouns and multi-token phrases can contribute typed candidates or
  PNF constraints without requiring every token to have a QID.
- Meaningful eventualities are locally typed from shared annotations even when
  no external occurrence identity is available.
- Coverage pressure and closure pressure are reported separately; residual
  closure work does not erase weakly typed candidate-world content.
- Backend requests are deduplicated, cache-aware, rate-limited, and
  microbatched without exposing backend concepts to parser code.
- Event reconciliation preserves temporal/spatial/participant/type/lineage and
  observation-occurrence roles; a scalar score cannot close identity.
- GWB repeated mentions converge when document evidence supports convergence;
  `9/11` remains distinct from `911` unless context supports the alternative.
- Unresolved external identity does not erase local PNF/claim structure.
- Partial coverage or evaluation-budget exhaustion yields an explicit
  abstention/hold, not a negative identity claim.
- No entity candidate, resolution result, PNF refinement, external registry
  row, or targeting result grants promotion or execution authority.
- Cross-context identity attachment is opt-in, bounded, receipted, reversible,
  and disabled by default.

## Deferred work

- broad live registry lookup during ordinary parsing;
- eager all-span or all-candidate materialization;
- embedding, LLM, or graph traversal before cheap/local stages are measured;
- shared emitted `review_alignment` before semantic convergence;
- global identity merging, person scoring, predictive judgment, or automatic
  cross-domain timelines;
- storage-format optimization beyond the evidence supplied by profiling.
