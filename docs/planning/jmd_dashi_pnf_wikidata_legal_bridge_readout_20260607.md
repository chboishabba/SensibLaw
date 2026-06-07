# JMD / DASHI / PNF Legal-Wikidata Bridge Readout

Date: 2026-06-07
Status: documentation with DASHI fixture bridge implemented; SensibLaw extractor pending

## Purpose

Record the current readout before implementing any new bridge work across:

- SensibLaw legal-text extraction and processing;
- ITIR Predicate Normal Form (PNF) / residual carriers;
- Wikidata review and migration lanes;
- GWB and affidavit review lanes;
- JMD's Senate formalism from the 2026-06-06 paste; and
- the sibling DASHI Agda formalism in `../dashi_agda`.

The paste fetched from:

`https://pastebin.xware.online/paste/20260606_000330_senate_formalization`

is JMD's formalism. It should be treated as adjunct to the DASHI formalism,
not as an unrelated standalone proof island. In the working interpretation for
this repo, JMD and DASHI are mirror / inverse formal surfaces. Both are
evidence-bearing formal carriers that can support SensibLaw review artifacts,
but neither should be collapsed into SensibLaw truth authority or live
Wikidata edit authority.

Downloaded local copies for this inspection pass:

- `/tmp/senate_formalization`
- `/tmp/senate_formalization.raw`

## 2026-06-07 DASHI Update

After this readout was first drafted, `../dashi_agda` gained a checked
fixture-level adapter:

- `DASHI/Interop/SenateFormalizationPNFAdapter.agda`

That adapter represents JMD's Senate Lean bundle as a source-side PNF adapter,
not as legal truth. It records local attribution and references:

- formalizer attribution: `JMD Senate formalization`;
- local monster reference: `monster submodule: meta-introspector/monster`;
- local Lean bridge reference: `../dashi_lean4`.

It also exposes the attribution as part of the typed adapter surface through:

- `formalizerAttributionStatement`;
- `localReferenceSurfaces`.

The adapter maps representative Senate Lean declarations into the existing
PredicatePNF carrier shape and proves fixture residuals for:

- exact;
- partial;
- no typed meet;
- contradiction.

It keeps:

- `legalAuthorityPromotion = false`;
- `wikidataLiveEditAuthority = false`.

The adapter is wired into:

- `ITIRPNFAssessment.agda` as `senateFormalizationLane`;
- `DASHI/Everything.agda` as an aggregate import.

Reported validation passed in `../dashi_agda`:

```bash
agda DASHI/Interop/SenateFormalizationPNFAdapter.agda
agda ITIRPNFAssessment.agda
agda DASHI/Everything.agda
```

This means the missing join is no longer purely prose on the DASHI side. The
remaining gap is now specifically a SensibLaw runtime / artifact gap: no
script yet parses or indexes the full Senate Lean bundle, computes declaration
body hashes, or emits a JSON source-unit index to check against the Agda
fixture surface.

## Current SensibLaw Spine

The current canonical PNF note is:

- `SensibLaw/docs/pnf_itir_primer.md`

The implementation anchor is:

- `SensibLaw/src/text/residual_lattice.py`

The important boundary is already stated correctly: PNF is a typed predicate
carrier and residual comparison surface. It is not a separate reasoning oracle,
parser, truth authority, or edit authority.

The current `PredicatePNF` carrier includes:

- predicate;
- structural signature;
- typed role bindings;
- qualifiers including polarity, modality, temporal scope, and jurisdiction
  scope;
- wrapper state and evidence-only flag;
- modifiers;
- provenance;
- optional atom id;
- optional domain fence; and
- optional latent support metadata.

Residual comparison is ordered:

```text
exact < partial < no_typed_meet < contradiction
```

This gives SensibLaw a governed middle layer:

```text
source / formal artifact / parser observation
  -> structured carrier or receipt
  -> PredicatePNF
  -> residual review
  -> bounded review artifact
  -> optional downstream promotion under a separate gate
```

## Legal Extraction State

The legal extraction lanes are close to the shared PNF shape, but they are not
yet uniformly first-class `PredicatePNF` emitters.

Observed current surfaces:

- fact intake has a small stable observation predicate set;
- AU and GWB semantic lanes emit predicate keys, entities, receipts, and
  promoted / review statuses;
- affidavit coverage review emits relation buckets, normalized review
  surfaces, compiler contracts, and product gates;
- GWB handoff emits checked public slices, selected promoted relations,
  review lanes, and Zelph handoff files;
- Wikidata climate review already has a good pattern:
  candidate change surface + text-side predicate carrier + residual
  completeness surface + review disposition.

The main architectural gap is not absence of extraction. It is inconsistent
normalization at the shared boundary. Several lanes carry:

```text
predicate_key + receipts + custom payload
```

where the cross-lane bridge wants:

```text
PredicatePNF-compatible carrier + provenance + wrapper + residual result
```

## Wikidata Boundary

The Wikidata lane is correctly review-first.

The practical Wikidata guide states that migration packs, review packets,
structural hotspot packs, disjointness diagnostics, and change-review packets
are bounded review artifacts. They are not edit bots and do not turn LLM,
DBpedia, SUMO, subclass, constraint, disjointness, or PNF signals into
authority by themselves.

Current useful implemented pattern:

```text
bounded Wikidata slice
  -> migration_pack candidate rows
  -> text-side predicate carriers
  -> residual/completeness bridge cases
  -> held / promotable / mixed review disposition
```

The newer typed claim reconciliation surface also pins the correct Wikidata
boundary:

- `truth_claimed = false`;
- `live_edit_authority = false`;
- preferred / normal rank is observed evidence metadata only;
- deprecated rank is held-for-review metadata only;
- qualifiers and references are source substrate, not proof.

This matches the DASHI Agda carrier fields:

- `truthClaimed ≡ false`;
- `liveEditAuthority ≡ false`;
- promotion state remains `promotionFalse`.

## DASHI Formalism Anchor

Relevant sibling formalism files in `../dashi_agda`:

- `.planning/CLAIM_RECONCILIATION_SENSIBLAW_ALIGNMENT_20260606.md`
- `ClaimReconciliationObjectLattice.agda`
- `LargerObjectClassificationLattice.agda`
- `DialecticalJourneyLoom.agda`
- `LoomRelationAlgebra.agda`
- `ClassificationDiscoveryLattice.agda`
- `ITIRPNFAssessment.agda`

The DASHI claim-reconciliation carrier defines bounded objects for:

- `ClaimAtom`;
- `ResponseUnit`;
- `ClaimRoot`;
- `ClaimRelationAssessment`;
- `TypedObjectAssertion`;
- `WikidataQualifier`;
- `WikidataReference`;
- `WikidataRevisionWindow`;
- `WikidataStatementRow`.

Canonical examples include:

- `X walked the dog` vs `X did not walk the dog`, classified as an
  explicit dispute without deciding truth;
- `6 is a 1-morphism`, kept witness-pending without category / bicategory
  context and typing rule;
- Wikidata QID/PID/value/qualifier/reference/revision rows with truth and live
  edit authority explicitly false.

`LoomRelationAlgebra.agda` gives the finite relation vocabulary:

- `exactSupport`;
- `equivalentSupport`;
- `explicitDispute`;
- `implicitDispute`;
- `partialOverlap`;
- `adjacentEvent`;
- `substitution`;
- `proceduralNonanswer`;
- `unrelated`.

It also separates relation root, bucket, evidence status, and promotion state.
The canonical relation algebra states that support is a comparison relation
only, not theorem promotion.

`ClassificationDiscoveryLattice.agda` confirms the residual chain:

```text
exact -> partial -> noTypedMeet -> contradiction
```

and keeps PNF receipt diagnostics runtime-bound and boundary-only.

## JMD Formalism From Paste

The JMD paste is a Lean 4 formalization of Senate procedural source structure
from CRS "Parliamentary Reference Sources: Senate" (`RL30788`).

The paste reports roughly 1,300 lines across these modules:

- `RequestProject/Basic.lean`;
- `RequestProject/Recognition.lean`;
- `RequestProject/Voting.lean`;
- `RequestProject/SenateManual.lean`;
- `RequestProject/UCagreements.lean`;
- `RequestProject/Enforcement.lean`;
- `RequestProject/Committees.lean`;
- `RequestProject/RulemakingStatutes.lean`;
- `RequestProject/Riddick.lean`;
- `RequestProject/Main.lean`.

The modeled concepts include:

- nine Senate procedural sources;
- floor enforceability;
- rulemaking authority;
- precedent weight hierarchy;
- recognition priority;
- voting thresholds;
- Senate Manual structure;
- unanimous consent agreements;
- enforcement mechanisms;
- committee rule publication and internal enforcement;
- rulemaking statutes;
- Riddick coverage and citation structure.

Important interpretation: JMD's Lean theorem surface is not a SensibLaw
promotion surface by itself. It should be admitted as a formal source-unit
carrier with provenance and mapped into PNF-compatible atoms for residual
comparison. This mirrors how DASHI gives Agda-side carrier discipline without
turning the carrier into runtime truth.

## Mirror / Inverse Working Model

Working interpretation for this repo:

- DASHI is the carrier / lattice / non-promotion formal side for claim,
  relation, object-family, PNF, and Wikidata row discipline.
- JMD is the source-side legal/procedural formalization side, here represented
  by Senate procedure concepts in Lean.
- SensibLaw is the runtime reducer / review artifact surface.
- Wikidata is a bounded external source substrate and review target, not a
  predicate authority.

The mirror / inverse relationship can be read operationally as:

```text
JMD: source-domain formal declarations over legal/procedural material
  -> formal source units
  -> PredicatePNF-compatible carriers

DASHI: carrier, lattice, relation, and promotion-boundary formal declarations
  -> admission discipline for those carriers
  -> non-promotion / residual review invariants

SensibLaw: deterministic runtime builders
  -> review packets, handoffs, compiler contracts, fixtures
  -> governed promotion gates
```

## Proposed Bridge Shape

Add a read-only source-to-PNF bridge for formal legal/procedural artifacts.
The DASHI fixture adapter now exists; the SensibLaw side still needs a runtime
indexer and JSON artifact bridge.

Target flow:

```text
Lean / Agda formal artifact
  -> formal_source_unit
  -> declaration index
  -> PredicatePNF carrier
  -> residual review
  -> optional Wikidata / affidavit / GWB review packet join
```

The bridge should preserve:

- source artifact identity;
- declaration or constructor name;
- module path;
- declaration kind (`def`, `theorem`, `structure`, `inductive`, record,
  canonical example, etc.);
- source span or stable excerpt when available;
- body hash or statement hash;
- formalism family (`jmd`, `dashi`, or later families);
- explicit non-promotion wrapper;
- provenance notes.

Suggested initial PNF predicate families for JMD Senate material:

- `senate_procedural_source`;
- `floor_enforceability`;
- `rulemaking_authority_source`;
- `precedent_weight_order`;
- `recognition_priority`;
- `vote_threshold_required`;
- `manual_component`;
- `uc_agreement_property`;
- `committee_rule_publication_requirement`;
- `committee_rule_enforcement_scope`;
- `rulemaking_statute_category`;
- `riddick_coverage_fact`.

Suggested initial PNF predicate families for DASHI claim/legal carrier
material:

- `claim_atom`;
- `response_unit`;
- `typed_relation`;
- `typed_object_assertion`;
- `wikidata_statement_row`;
- `wikidata_qualifier`;
- `wikidata_reference`;
- `wikidata_revision_window`;
- `pnf_residual_level`;
- `promotion_boundary`.

## Governance

The bridge must not:

- treat JMD Lean theorems as legal truth;
- treat DASHI Agda records as SensibLaw runtime truth;
- use Wikidata QIDs/PIDs as predicate authority;
- fabricate source receipts;
- infer live Wikidata edit authority;
- mark claims, legal propositions, or formal declarations as promoted without
  a separate downstream gate;
- silently collapse caller hints into derived reconciliation.

The bridge may:

- emit evidence-only `PredicatePNF` carriers;
- emit review-only observation rows;
- compare carriers through `src/text/residual_lattice.py`;
- feed bounded review packets;
- propose held / reviewable / promotable dispositions under existing local
  gates;
- expose gaps such as missing temporal qualifiers, missing source receipts,
  missing typing context, or no typed meet.

## First Implementation Slice

Keep the first SensibLaw runtime slice small and read-only.

The DASHI-side fixture-level `formal_source_unit` representation now exists in
`DASHI/Interop/SenateFormalizationPNFAdapter.agda`. The next SensibLaw slice is:

1. Store or reference the JMD Senate Lean bundle as a bounded local source
   artifact.
2. Index a handful of declarations:
   - `ProceduralSource`;
   - `ProceduralSource.floorEnforceable`;
   - `rulemaking_implies_floor_enforceable`;
   - `VoteThreshold`;
   - `SenateAction.requiredThreshold`;
   - `canonicalDogExplicitDisputeRelation`;
   - `canonicalSixOneMorphismAssertion`;
   - `canonicalWikidataStatementRow`.
3. Compute stable declaration hashes for the indexed Lean declarations instead
   of using fixture hashes.
4. Emit a JSON source-unit index that can be checked against the DASHI adapter
   surface.
5. Emit `PredicatePNF`-compatible atoms for those declarations in SensibLaw's
   runtime dictionary shape.
6. Add residual tests for:
   - exact meet;
   - partial meet;
   - no typed meet;
   - contradiction or polarity conflict where appropriate.
7. Add a summary artifact showing:
   - formalism family;
   - source module;
   - carrier count;
   - residual counts;
   - non-promotion boundary flags.

Defer:

- database migration;
- live Wikidata interaction;
- broad Lean/Agda parser;
- global QID-only automation;
- any public claim of legal sufficiency or theorem import.

## ZKP Frame

O:
- User and repo maintainers decide promotion.
- SensibLaw implements runtime carriers and review artifacts.
- `../dashi_agda` supplies DASHI formal carrier discipline.
- JMD's Senate Lean formalism supplies adjunct legal/procedural source
  formalization.
- Wikidata remains external substrate and review target.

R:
- Document the current formalism and bridge boundary before implementation.
- Preserve mirror / inverse JMD-DASHI interpretation.
- Keep all formal-source carriers non-promoting until governed downstream.

C:
- SensibLaw docs, PNF implementation, fact-intake typed reconciliation,
  Wikidata builders, GWB and affidavit lanes.
- DASHI Agda carrier files in `../dashi_agda`.
- Downloaded JMD paste in `/tmp/senate_formalization.raw`.

S:
- PNF and residual semantics are implemented.
- Wikidata review/migration lanes are bounded and non-authoritative.
- Typed claim reconciliation is already aligned with DASHI.
- JMD Senate formalism is available as a source-side Lean formal artifact.
- DASHI now has `DASHI/Interop/SenateFormalizationPNFAdapter.agda`, wired into
  `ITIRPNFAssessment.agda` and `DASHI/Everything.agda`.
- The SensibLaw runtime extractor / JSON source-unit index is not yet
  implemented.

L:
- undocumented -> documented -> DASHI fixture-indexed -> SensibLaw
  source-indexed -> PNF-emitting -> residual tested -> review-packet
  integrated.

P:
- Treat the DASHI fixture bridge as the checked formal-adapter surface.
- Start the SensibLaw engineering step with a small read-only source-unit JSON
  indexer for the Senate Lean bundle.
- Reuse existing `PredicatePNF`, residual lattice, and review packet surfaces.
- Treat JMD/DASHI as adjunct formal surfaces with inverse roles, not as
  replacement runtime authorities.

G:
- No live Wikidata edits.
- No truth promotion from formal carriers alone.
- Tests must verify non-promotion flags and residual outcomes before any
  runtime integration claim.

F:
- DASHI fixture adapter exists, but there is no SensibLaw-emitted JSON
  source-unit index yet.
- No real declaration body hashes are computed yet for the Senate Lean bundle.
- No formal-source-unit schema yet.
- No parser/indexer for Lean/Agda declarations in SensibLaw yet.
- No SensibLaw test yet checks a runtime-emitted JMD Senate source-unit index
  against the DASHI adapter fixture surface.
