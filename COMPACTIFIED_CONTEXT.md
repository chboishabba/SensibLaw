# COMPACTIFIED_CONTEXT

## 2026-07-15 — WD bridge architecture context refresh

- Resolved archived thread:
  - title: `WD Bridge Architecture`
  - online UUID: `6a54b21f-ba30-83ec-b08e-0e62cb9d0933`
  - canonical thread ID: `71e63a13e10f7370ace24a676750577ca63e3317`
  - source: `db`, snapshot `pull_20260714T035959Z` (141 archived rows; the
    resolver's latest six-row snapshot was incomplete)
  - live refresh attempted on 2026-07-15 but ingested zero messages; do not
    describe the archive as freshly web-verified
- Main decisions retained:
  - every mature lane needs the shared external-authority bridge *capability*,
    but external traversal remains conditional on the candidate and never
    substitutes for local evidence, role, authority, or promotion;
  - external identity attachment and structural pressure are separate,
    revision-bound products;
  - pressure is multi-view and domain-bounded: WD class/property structure is
    the first substrate, with Wikipedia/Simple/Abstract Wiki, translation, and
    domain cohorts later contributing reviewable expected-shape pressure;
  - a checked external graph slice is one input to a forkable basis revision;
    public channels project basis revisions and attestations but do not turn
    subscriber counts into truth.
- Archive hygiene:
  - the first pages contain hidden Project/NotebookLM source dumps, including
    the unexpected Agda text. These are tool/file-context records, not
    user-visible thread authorship and not architecture evidence.

## Purpose
Compact snapshot of the current architecture and next seam.

## Current state
- one media-adapter layer canonicalizes ordinary inputs into `CanonicalText`
- one parser spine operates over `CanonicalText`
- extraction profiles sit above the parser spine; parser logic is structural,
  not semantic
- mixed-content ordinary documents are first-class:
  - prose, inline code, quotes, tables, lists, headings, citations all survive one parser
- code is not a source class or parser family
- provenance is metadata, not parser identity
- structure is discovered from parsed output and graph relations, not declared
  as an input type

## Parser doctrine
- parser input: `CanonicalText`
- parser output: one parsed observation stream with stable segments, units, and anchors
- block `segment_kind`:
  - `heading`
  - `paragraph`
  - `list`
  - `quote`
  - `table`
  - `code_block`
  - `divider`
- inline `unit_kind`:
  - `text_run`
  - `code_span`
  - `citation`
  - `link`
  - `emphasis`
- separate parsers are justified only for truly different primary mechanics,
  not prose-with-code
- adapter distinctions such as PDF, HTML, rows, or transcripts are not
  top-level parser doctrine

## Active lanes
- affidavit/Wikidata typed reconciliation:
  - current contract:
    `docs/planning/affidavit_wikidata_typed_reconciliation_contract_20260606.md`
  - current helper:
    `src/fact_intake/typed_claim_reconciliation.py`
  - purpose: operational Python carrier layer for proposition/response rows,
    object-type assertions, and Wikidata statement rows that stays aligned with
    the DASHI formal object grammar
  - relation labels are the canonical affidavit finite vocabulary:
    `exact_support`, `equivalent_support`, `explicit_dispute`,
    `implicit_dispute`, `partial_overlap`, `adjacent_event`, `substitution`,
    `procedural_nonanswer`, `unrelated`
  - dog fixture boundary: `walked the dog` versus `did not walk the dog`
    reduces to `explicit_dispute` / `invalidates` / `disputed`; it does not
    decide truth
  - object-type boundary: `6 is a 1-morphism` is a typed-object assertion, not
    a proof. It remains witness/context pending unless a category or
    bicategory context and typing rule are supplied
  - Wikidata boundary: QID/PID/value rows are provenance/evidence carriers with
    qualifier/reference metadata; rank and deprecation do not become truth,
    contradiction, proof, edit authority, or promotion
  - current formalism review result against DASHI:
    - relation algebra alignment: passed
    - dog dispute fixture: aligned
    - object-type witness/review/promotion fields: now materialized
    - Wikidata `truth_claimed = false` and `live_edit_authority = false`: now
      materialized
    - caller hints: now marked with `relation_derivation = caller_hint`
  - remaining honest seams:
    - add first-class statement IDs and revision windows when importers supply
      them
    - thread envelopes into persisted affidavit read-model tables only after a
      storage contract is explicit
    - add direct Python-vs-DASHI field grammar fixture coverage
- bounded Wikidata ontology-repair candidate comparison:
  - `wikidata compare-candidates` now evaluates a review-only
    `ChangeReviewPacket` against a bounded slice
  - current fixture is synthetic `Q27968055`
  - candidate mutations are in-memory only and reports carry
    `edit_authority: false`
  - this is Level 0 of the broader global structural-coherence roadmap, not a
    QID-only repair bot or Wikidata edit authority
  - bounded `mereology` / `temporal_exclusivity` coverage is now wired for
    `P361`/`P527`-style review packets, using curated policy only inside the
    supplied slice
  - reports can now carry pressure attribution buckets and candidate
    `held_*`/review reasons, so Q27968055-style local fixes can still surface
    upstream ontology pressure without turning that caveat into edit authority
- semantic-memory bridge:
  - future lane is pinned at
    `docs/planning/semantic_memory_bridge_future_lane_20260506.md`
  - first helper builds `sl.semantic_memory_index.v0_1` from supplied atoms,
    grounding candidates, and ontology closure paths
  - retrieval returns source snippets plus explanation paths, e.g.
    "great dane" matching a "dogs" query through `Great Dane -> dog breed -> dog`
  - boundary remains private memory retrieval only: no live entity linking, no
    fabricated QIDs/PIDs, no public Wikidata truth, and no belief inference
- operator-only relation-equivalence work on one ambiguous seed
- additive relation graph and structure metrics over the shared spine
- bounded extraction-profile layer above the parser spine
  - `normative_policy` now landed for `policy_statements` and `ir_queries`
  - `legal_review` now landed for `review_text`-first projection
- bounded ISO lane:
  - real ISO 42001 excerpt-pack fixtures are already landed on the same
    `normative_policy` projector
  - external ISO catalogue / PAS pages are reconnaissance only
  - ISO stays a bounded normative adopter/reuse lane, not a separate parser
    family or standards-catalog ingestion program
- verification gate
- docs/governance thresholding

## Holds
- OCR
- emitted `review_alignment`
- gate/resolution churn
- reporting/UI widening
- provenance-specific parser branches
- code-specific top-level source families
- structuredness as an input taxonomy

## Next implementation seam
- run one-seed operator-only relation equivalence on
  `gwb_us_law:nsa_surveillance_review`
- add the smallest clustering/invariant readout helper above relation
  similarity
- keep the ISO lane bounded to normative reuse/recon and fixture-quality
  review
- widen downstream consumers only where canonical refs materially reduce
  duplicate parsing
# 2026-07-17 climate-GHG orthogonal assessment V2 decision

- The immutable 232-family / 3,562-statement company-direct replay remains the
  source substrate; V2 is installed only below `derived/orthogonal_v2/`.
- Generic shared policy code owns orthogonal carrier validation, deterministic
  ordering/hashes, authority checks, and aggregation. Climate profile code owns
  GHG QIDs, semantic derivation, predicates, and A1-A5/H4 projections.
- Eligibility is candidate-review-only and cannot create promotion, execution,
  edit, or source-quality authority. Reference adequacy is structural only.
- Canonical contract:
  `docs/planning/climate_ghg_orthogonal_assessment_v2_20260717.md`.
- The evidence/governance follow-on is bounded to the existing 15-family sample
  and immutable replay. Canonical adjudications are versioned JSON sidecars;
  diagnostic reports separate exclusive primary holds from overlapping reasons,
  explain unknown coverage and A4 attrition, and propose a first contract only
  after a five-positive / 95%-precision / zero-critical-miss gate. A proposed
  canary is review-only and capped at 25 statements; CSV/OpenRefine is deferred.
- The next resolution tranche is offline and transition-based:
  `docs/planning/climate_ghg_policy_resolution_dry_run_20260717.md`. It tests
  132 fiscal-only holds, one Q52579 subject adjudication covering 21
  statements, one Q1476113 reference adjudication covering 4 statements, and
  concentrated method/unit mappings (12/3). The 176 fiscal-plus-ambiguous-scope
  statements remain held. Outputs partition transitions into policy-resolved,
  evidence-resolved, still-held, and newly-unsupported; no transition grants
  edit, promotion, or execution authority.
- Broader TODO sequencing is now explicit in
  `docs/planning/itir_broader_todo_priority_20260717.md`: shared compiler and
  PNF-driven entity-resolution spine first; GWB/affidavit as the
  ambiguity-heavy proving tranche; AU as the next resolver/targeting adopter;
  Nat/Wikidata as an optional pinned registry backend and bounded diagnostic;
  graph expansion and hard ontology remainders after those gates. Shared
  emitted alignment, live migration, and broad ontology automation remain
  held.

# 2026-07-17 PNF-driven entity-resolution spine decision

- Canonical contract:
  `docs/planning/pnf_driven_entity_resolution_spine_20260717.md`.
- P0 begins at canonical spans, not review-target selection:
  `partial PNF -> typed resolution demand -> bounded candidate set ->
  resolution assessment -> refined PNF -> claim/target resolution`.
- Every token remains traceable and every logically meaningful span remains
  recoverable. Candidate objects are instantiated lazily so logical
  exhaustiveness does not require quadratic eager storage.
- Ordinary nouns and phrases may contribute instance, class, property, role,
  event-type, literal, or document-local candidates. Stopwords normally remain
  grammatical/relational evidence.
- Candidate identity, resolved identity, and promoted fact are separate
  authority states. Ambiguity and unresolved identity remain first-class
  records and cannot silently alter PNF or source text.
- PNF is both a local semantic carrier and the query planner, pruning surface,
  cache signature, evaluation budget, residual inventory, and stopping
  criterion for entity resolution.
- Correction: residual pressure is not the admission policy. Coverage pressure
  attempts local typing for every meaningful entity, relation, quantity, role,
  and eventuality; closure pressure prioritizes deeper work that helps close a
  PNF. Both remain explicit.
- Parsers remain registry-blind. A registry-neutral broker serves local/cache
  evidence first and interleaves local compilation with deduplicated,
  backend-rate-limited microbatches. Adapter batching and compiler interleaving
  are complementary, not competing designs.
- Event typing consumes shared language annotations/reducer outputs rather than
  a new trigger-word parser. It distinguishes linguistic eventuality, event
  class, occurrence, observation, cluster, forecast, report, alert, and rolling
  state.
- WorldMonitor is an optional resolvable external world-model snapshot backend,
  not merely a feed and not an event ontology/authority. Its concrete adapter
  must follow inspection of the current sibling schema.
- Cross-registry event reconciliation is a typed meet over temporal, spatial,
  participant, event-type, mention, provenance-lineage, and
  observation/occurrence obligations. Scalar confidence may prioritize review
  but cannot close identity or promote a claim.
- GWB proves document-local coreference and narrative/event ambiguity; AU
  proves reuse under typed legal constraints; Nat/Wikidata provides optional,
  revision-pinned external evidence. No tranche owns the resolver.
- Parser prerequisite: converge the two section-parser implementations, retain
  one canonical character-coordinate system, share immutable text and external
  snapshots by reference, and preserve verbose JSON only as a compatibility
  projection.
- First P0a implementation slice complete: `src.ingestion.section_parser` is
  now the sole parser/rule-extraction/structural-node implementation.
  `src.section_parser` is a compatibility projection preserving historical
  `Provision` trees and simple section JSON. The remaining P0a work is
  span-only storage, one-pass views, and versioned caching.
- First P0b implementation slice complete: `src.policy.entity_resolution`
  provides generic receipt-free `MentionSpan`, `EntityCandidate`,
  `EntityCandidateSet`, and document-local `CoreferenceCluster` carriers.
  The deterministic candidate-only carrier rejects cross-document clusters and
  non-candidate authority. It does not generate spans, resolve identity, query
  registries, alter PNF, or promote claims.
- P0b.1 implementation complete: the same generic module now has a
  backend-free licensing carrier over public parser/reducer output. It
  materializes non-structural lexical spans, numeric spans, maximal
  name-shaped phrases, and parser-annotated eventualities, while recording the
  complete recoverable token lattice and structural suppression. Licensing is
  not candidate acceptance, lookup, resolution, PNF mutation, or promotion.
  Alias/grammar/PNF-demand expansion and generated-mention recurrence
  clustering remain next.
- P0b.2 implementation complete: generated mentions can be grouped by the
  same case-folded, whitespace-normalized surface inside one document. These
  recurrence groups are only local evidence: they do not establish aliasing,
  coreference, external identity, PNF content, or promotion, and they cannot
  cross a document boundary.
- P0b.3 decision: represent alias/grammar/PNF-demand widening as explicit,
  source-anchored token-interval requests. A request records why a span should
  be licensed, but does not itself establish an alias, identity, PNF binding,
  candidate, or promotion. Alias-index and grammar producers remain separate
  adapters; PNF construction remains P0c.
- P0b.4 decision: an alias index is a caller-supplied lexical/provenance input,
  not a resolver. Exact normalized token-sequence matches may emit only
  `alias_hint` expansion requests. Entries carry expected candidate kinds and
  context evidence, never QIDs, candidate rankings, identity assertions, or
  registry calls; `9 / 11` therefore cannot silently collapse to `911` or a
  particular event. Structural-grammar request production is completed
  separately; bounded candidate retrieval is the next stage.
- P0b.5 decision: structural grammar consumes public parser/token annotations
  and emits bounded nominal-phrase requests only. The initial profile is
  maximal contiguous determiner/adjective/numeral/noun/proper-noun spans with
  a noun/proper-noun head. It is syntactic admission, not entity/role identity,
  candidate selection, PNF binding, registry work, or promotion; absent
  annotation yields no invented phrase boundary.
- P0b.6 decision: bounded candidate retrieval is an offline exact
  canonical-token match between anchored mentions and caller-supplied,
  provenance-bearing catalog entries. It returns a candidate set for every
  mention, including explicit zero alternatives, and preserves multiple exact
  alternatives without ranking or selection. Catalog identity/snapshot fields
  are candidate evidence only; this stage has no network, resolution,
  coreference, PNF, promotion, or execution effect. `9 / 11` remains distinct
  from `911` until later contextual assessment.
- P0b.7 decision: form derivation is a separate, source-anchored algebra ahead
  of entity retrieval. It emits ambiguous surface, token, numeric, date-shaped,
  abbreviation, and caller-profile-derived `FormCandidate` alternatives plus
  explicit `FormRelation` records. Deterministic serialization is never a
  semantic rank. No form transformation names an event/entity, establishes
  alias truth, performs metonymy, mutates PNF, resolves identity, or promotes a
  fact; those require later typed PNF/context obligations.
- P0b.7 refinement: composition must enumerate every compatible bounded form
  path. First-match, input order, and serialization order cannot suppress a
  linguistic alternative. P0b.8 will consume those alternatives into local
  type and independent coverage-pressure carriers; it remains candidate-only
  and does not create external identities, PNF closure, or authority.
- P0b.8 implementation: `LocalTypeAlternative`, `LocalTypingRule`, and
  `CoveragePressureAssessment` emit a locally typed candidate-world fragment.
  Structural reductions cover numeric quantity, abbreviation, calendar
  expression, and parser-annotated linguistic eventuality; profile rules may
  add generic local semantic families but cannot carry identity or promotion
  state. Coverage is independently receipted per mention, before PartialPNF.
- P0c.1 implementation: document-bounded `PartialPNF` slots retain compatible
  local type alternatives by reference rather than combining them. Closure
  pressure is a separate per-slot obligation inventory (`locally_closed`,
  `requires_external_resolution`, `requires_local_typing`, or `not_required`)
  with no demand, registry, resolution, claim, or promotion effect.
- P0c.2 implementation: `ResolutionDemand` is a backend-free projection only
  from unresolved P0c.1 closure states. It carries source PNF/slot/mention
  anchors, expected semantic families, requested facets, and budget class;
  it neither chooses a backend nor executes lookup/resolution/PNF mutation.
- P0c sequencing correction: typed resolution subjects and formal event roles
  precede scheduler design. Entity, event type, event occurrence, event
  artifact, document-local cluster, and property/relation subjects remain
  distinct; event artifacts preserve observation/cluster/forecast/report/
  alert/rolling-state roles and cannot be coerced into occurrences.
- Demand deduplication requires equality over typed subject/role, local type
  alternatives, PNF slot role, temporal/spatial/relation/source-scope
  constraints, requested evidence facets, and document scope. Surface form
  equality is insufficient. The cache/scheduler follows this semantic key.
- P0c.3/P0c.4 implementation: every unresolved demand now receives an explicit
  `ResolutionSubjectDeclaration`; event occurrences and event artifacts enforce
  distinct formal roles. `build_resolution_subject_carrier` emits typed
  subjects, demand links, and semantic equivalence-group receipts while
  preserving every member. Coalescing remains potential only: there is no
  scheduler, backend/cache effect, evidence retrieval, or resolution decision.
- P0c.5 implementation: `ResolutionCacheEntry`,
  `ResolutionBackendCapability`, and `build_resolution_schedule_carrier` now
  provide a registry-neutral, side-effect-free evidence control plane. Plans
  consume semantic equivalence groups and emit fresh/stale/negative cache,
  fetch-planned, unavailable, unsupported, and budget-exhausted states with
  deterministic microbatch receipts. No I/O, identity choice, reconciliation,
  PNF mutation, or promotion is possible; document-local evidence is the next
  resolver proof before external adapters.
- Anti-panopticon boundary: document-local resolution is allowed inside a
  declared tranche; cross-context joins remain explicit, opt-in, reversible,
  reviewable bridge proposals and are never global/default promotion.
- 2026-07-18 directory-kernel decision: directory compilation is generic
  orchestration over a shared per-document compiler, not a source type,
  semantic profile, or authority boundary. The initial phase inventories
  bounded non-symlink input, compiles each supported document locally,
  writes append-only content-addressed artifacts, and groups unresolved
  semantic demands. It performs no network work, external identity selection,
  readiness promotion, or cross-document identity closure. Paths remain
  provenance occurrences; content hash plus media-normalisation declaration
  supplies document identity. See
  `docs/planning/directory_compilation_kernel_20260718.md`.
- 2026-07-18 PostgreSQL semantic-compiler decision: the next P0 slice must
  build structured generic PNF factors from one annotation graph, plan sparse
  local typed meets, persist immutable factor revisions and build dependencies,
  and derive demands only after local refinement. The active contract is
  `docs/planning/postgres_semantic_compiler_p0_20260718.md`; GWB and AU remain
  proof fixtures rather than semantic profiles. The workspace previously had
  only the older legal PostgreSQL migrations, so the compiler substrate starts
  as an additive generic schema rather than claiming runtime parity.
- 2026-07-18 PostgreSQL runtime checkpoint: migration `007` is applied to the
  persistent user-owned PostgreSQL 18 development cluster. A `gwb-mini` proof
  persisted 3 documents, 40 PNF factors, and 29 unresolved demands; an
  identical rerun introduced no additional demand-projection build rows. The
  local service is a development surface only, never source-artifact or claim
  authority; broader reuse measurements and full proofs remain pending.
- 2026-07-18 first proper-corpus checkpoint: generic structural HTML
  canonicalisation enabled the raw six-document GWB public-bios collection to
  compile through the same PostgreSQL-backed local-only path. It produced
  11,676 factors, 8,719 unresolved demands, and 5,012 compatible local typed
  meets; no network, cross-document identity closure, or readiness ran. An
  identical rerun added no demand-projection builds. EPUB/PDF books, external
  evidence, and any GWB-specific semantics remain out of scope.
- 2026-07-18 local-quality decision: retain `uv.lock` as a reviewed Python
  dependency-resolution artifact in support of reproducible local PostgreSQL,
  CI, and future Nix development. Before any EPUB/PDF capability or external
  evidence work, improve generic local typing by projecting existing public
  annotation/relation structure into branch-preserving predicate-role,
  temporal/spatial, nominal, coordination, and composition alternatives. This
  remains candidate-only and must not choose identities or add corpus-specific
  semantics.
- 2026-07-18 local-quality checkpoint: the six raw GWB public-bios HTML
  sources recompiled under semantic compiler v0.2 with 5,317 provenance-backed
  generic role/structure hypotheses. `local_type_unresolved` fell from 7,355
  to 3,824; demands rose from 8,719 to 8,817 because local structure now
  preserves explicit external-identity obligations rather than masking them as
  generic untyped mentions. No EPUB/PDF, network, cross-document closure, or
  readiness work was added.
- 2026-07-18 parser-to-PNF decision: the next local semantic-compiler slice
  repairs information loss, not parser availability. One public parser pass
  must preserve token/sentence/POS/lemma/morphology/dependency/head and parser
  capability/model observations in the immutable annotation graph. The
  relational bundle becomes a projection of that graph and must retain
  predicate structure without a direct-object precondition. PNF reductions
  consume these observations as branch-preserving syntactic factors and
  constraints; pronouns are unresolved PNF arguments/reference branches, not
  English word-list classifications. Historic `markup_fragment` diagnostics
  are invalid where missing diagnostic input caused the classification.
- 2026-07-18 parser-to-PNF checkpoint: v0.5 now shares one public spaCy parse
  across compiler mention licensing and relation projection. The graph retains
  parser token/span/dependency/capability observations, predicate projection
  retains subject-only/oblique/complement structures, and PNF reductions add
  predicate-inflection, clausal host/content constraints, plus parser-derived
  pronominal reference alternatives.
  No antecedent, semantic-role, truth, identity, occurrence, external evidence,
  or readiness decision is made. Focused parser/reduction/compiler tests and
  the `gwb-mini` directory proof passed under the ITIR-suite root venv with
  `en_core_web_sm`.
- 2026-07-18 local-refinement decision: the next v0.5 slice treats pronouns as
  unresolved PNF argument/reference factors.  It may generate bounded
  same-document entity/eventuality/proposition binding candidates from parser
  position, morphology, syntactic accessibility and factor kind, but a
  candidate is never identity closure.  Constraint evaluation is immutable and
  separate from a constraint declaration; syntax/voice/morphology can narrow
  semantic-role alternatives without an English verb-role catalogue or an
  automatic passive-subject-to-agent rule.  Refinements must be factor-local,
  receipt-backed and revision-linked before demand projection.
- 2026-07-18 local-refinement checkpoint: v0.6 evaluates parser-supported PNF
  constraints independently, closes only `syntactic_argument_structure_unchecked`,
  and records a factor revision when it adds role or binding candidates.
  Document-local candidate generation distinguishes entity/eventuality/
  proposition references and emits incompatible bindings explicitly; it never
  asserts coreference.  Passive subjects retain patient/theme role branches,
  and expletive-compatible reference branches remain available without an
  invented antecedent.  The shared local-type carrier now includes propositions
  so composition observations compile generically.  GWB proper and AU-mini
  local proofs completed without network or readiness.
