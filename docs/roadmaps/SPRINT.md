# Sprint Status And Priority Order

## Current execution order
1. `A1` Shared compiler spine
2. `B1` Shared semantic surface definitions
3. `A2` AU normalization
4. `A3` GWB normalization
5. `B2-B3` Proving-lane adoption
6. `A4-A5` Nat adoption and shared promotion gate
7. `A6` Operator workflow consumption
8. `P1` UI / workbench widening

- P0 architecture lane 1 remains the cross-lane compiler normalization push:
  `evidence_bundle -> promoted_outcomes -> derived_products` across AU, GWB,
  and Wikidata/Nat.
- P0 architecture lane 2 remains shared cross-lane semantic surface
  extraction so `text_surface`, `candidate_surface`, `claim_surface`,
  `hint_surface`, and `decision_surface` become canonical shared types rather
  than lane-local facade shells.
- UI / `itir-svelte` / workbench followthrough stays below those P0 lanes and
  should consume and validate normalized products, not outrank them.

## Canonical sprint references
- `sprint_s7.md`
- `sprint_s9.md`

## Status note
- S7 and S9 remain useful sprint contracts, but they are not the current
  execution-order authority by themselves.
- If a UI sprint note conflicts with the architecture-first order above, the
  architecture-first order wins.

## Active P0 sprint checklist

### Track A: cross-lane compiler normalization

#### A1. Shared compiler spine
- Goal:
  freeze the shared
  `evidence_bundle -> promoted_outcomes -> derived_products`
  contract as the canonical cross-lane compiler shape.
- Scope:
  shared contract only; no lane-specific semantic widening beyond what AU,
  GWB, and Wikidata/Nat can all adopt honestly.
- Exit criteria:
  - AU, GWB, and Wikidata/Nat each have an explicit adoptable compiler-shaped
    contract.
  - the shared contract is documented as the current truth layer for
    compiler-shaped outputs.
  - no graph or UI surface is required to explain the contract itself.

#### A2. AU product normalization
- Goal:
  keep AU fact-review outputs normalized around the shared compiler spine.
- Scope:
  AU public handoff, AU fact-review bundle, and related promoted outcome
  readouts.
- Exit criteria:
  - AU emits the shared `compiler_contract` shape consistently.
  - AU-specific semantics remain lane-local, while product shape remains shared.
  - derived AU graph/operator surfaces stay explicitly downstream of compiler
    outputs.

#### A3. GWB product normalization
- Goal:
  keep GWB public and broader review outputs normalized around the same spine.
- Scope:
  GWB public handoff, public review, and broader review surfaces.
- Exit criteria:
  - GWB emits the shared `compiler_contract` shape consistently.
  - GWB-specific semantics remain lane-local, while product shape remains
    shared.
  - no GWB-only facade becomes the de facto compiler owner.

#### A4. Wikidata/Nat adopter pass
- Goal:
  make Wikidata/Nat a real adopter family of the compiler-shaped contract
  instead of a parallel architecture.
- Scope:
  revision/text/evidence bundle in, promoted migration/split/hold style
  outcomes out.
- Exit criteria:
  - Wikidata/Nat emits a compiler-shaped payload under the same top-level
    contract.
  - Nat-specific grounding/migration semantics remain adopters, not a new
    organizing abstraction.
  - any graph/report surfaces stay derived from the promoted outputs.

#### A5. Shared promotion gate
- Goal:
  harden the reusable `promote | abstain | audit` gate above normalized
  products.
- Scope:
  shared gate semantics, shared gate record, and fail-closed behavior above AU,
  GWB, and Wikidata/Nat normalized outputs.
- Exit criteria:
  - the shared gate record is stable across the adopter lanes.
  - no lane silently promotes around the gate.
  - abstention/audit remain explicit rather than implicit null behavior.

#### A6. Operator-grade consumption
- Goal:
  consume normalized compiler outputs in operator surfaces without letting the
  consumer become a new truth layer.
- Scope:
  read-model/operator/workbench consumption only after A1-A5 stay stable.
- Exit criteria:
  - operator/workbench surfaces consume compiler outputs rather than rederive
    their own incompatible product contract.
  - guided inspect/decide/record/follow-up flows stay downstream of normalized
    products.
  - UI remains subordinate to the contract, not vice versa.

### Track B: shared cross-lane semantic surface extraction

#### B1. Shared surface definitions
- Goal:
  define canonical shared owners for:
  `text_surface`, `candidate_surface`, `claim_surface`, `hint_surface`, and
  `decision_surface`.
- Scope:
  semantic surface ownership and contracts only; do not mass-rename call sites
  before canonical owners are fixed.
- Exit criteria:
  - each shared surface has an explicit canonical owner.
  - lane-local facade files are no longer treated as substrate by default.
  - the docs clearly distinguish shared types from lane adapters.

#### B2. First proving-lane adoption
- Goal:
  prove that at least one non-affidavit lane can adopt a shared surface
  honestly.
- Scope:
  affidavit plus AU fact-review/legal-follow is the preferred first proving cut.
- Exit criteria:
  - one shared surface is consumed by affidavit and one non-affidavit lane.
  - no second lane-specific type is introduced for the same concept.
  - adapter logic stays adapter-local rather than leaking back into the shared
    type.

#### B3. Second non-affidavit adopter
- Goal:
  prove the surfaces are actually cross-lane by landing a second
  non-affidavit adopter.
- Scope:
  GWB broader review or Wikidata/Nat, whichever fits the concept honestly.
- Exit criteria:
  - at least two non-affidavit lanes consume one shared surface.
  - the shared type survives lane differences without collapsing into
    affidavit-only semantics.
  - the success condition from `SensibLaw/todo.md` is met.

#### B4. Adapter conversion and cleanup
- Goal:
  demote old lane-local facades into adapters after shared ownership is proven.
- Scope:
  targeted adapter conversion only; no mass churn for naming symmetry.
- Exit criteria:
  - legacy facades are visibly adapter shells rather than truth-layer owners.
  - downstream consumers point at shared surfaces where appropriate.
  - temporary facade files do not harden into pseudo-substrates.

## Ordered run list
1. `A1` Shared compiler spine
2. `B1` Shared semantic surface definitions
3. `A2` AU normalization
4. `A3` GWB normalization
5. `B2-B3` Proving-lane adoption
6. `A4-A5` Nat adoption and shared promotion gate
7. `A6` Operator workflow consumption
8. `B4` Adapter conversion and cleanup

## Explicitly demoted to P1 until the above is stable
- guided next-action UX
- annotation / QA workbench widening
- broader `itir-svelte` hardening that does not directly validate or consume
  normalized products
- new UI-first semantics or parallel consumer-owned truth layers
- any wider operator-workbench expansion that is not directly required to
  validate the normalized compiler contract or shared semantic surfaces

# Current Sprint: A1 — Shared Compiler Spine

## Goal
Freeze the shared cross-lane compiler contract:
`evidence_bundle -> promoted_outcomes -> derived_products`
so AU, GWB, and Wikidata/Nat all converge on one honest top-level product
shape before more UI or lane-local abstraction growth.

## Why this sprint is next
- It is the first item in the current execution order.
- `B1` depends on knowing which compiler-shaped surfaces must stay shared at the
  product boundary.
- `A2`, `A3`, and `A4-A5` become churn-prone if they normalize against moving
  or lane-local top-level contracts.

## Scope
- In scope:
  - define the canonical top-level compiler contract and field ownership
  - specify the minimum shared semantics for `evidence_bundle`,
    `promoted_outcomes`, and `derived_products`
  - document allowed lane-local extensions below that shared contract
  - identify existing AU, GWB, and Wikidata/Nat emitters/adapters that must
    conform
- Out of scope:
  - operator UX widening
  - annotation / QA workbench expansion
  - new graph-first or UI-first payload definitions
  - large adapter cleanup beyond what is required to freeze the contract

## Deliverables
- A versioned shared compiler contract doc that names:
  - required top-level fields
  - required invariants
  - permitted lane-local extension points
  - promotion-gate handoff expectations
- A lane-mapping table for AU, GWB, and Wikidata/Nat showing:
  - current producer entrypoints
  - current emitted top-level shapes
  - gaps versus the shared contract
  - intended normalization path
- A repo-facing doctrine note that the compiler contract is the truth layer for
  cross-lane promoted products, while graph/UI/workbench surfaces are derived
  consumers

## Implementation checklist
1. Locate the current AU, GWB, and Wikidata/Nat producer/runtime seams that
   already emit or approximate `evidence_bundle`, `promoted_outcomes`, and
   `derived_products`.
2. Extract the true common top-level fields rather than unioning every
   lane-local convenience field into the shared contract.
3. Write the canonical contract and invariants in repo docs with explicit
   examples for each lane.
4. Record lane-by-lane deltas so `A2`, `A3`, and `A4` can normalize against a
   frozen target instead of rediscovering it independently.
5. Mark any known UI/workbench-only shaping as downstream/derived rather than
   part of the compiler truth layer.

## Exit criteria
- AU, GWB, and Wikidata/Nat each have an explicit mapping to one shared
  compiler-shaped top-level contract.
- The repo docs clearly distinguish required shared fields from lane-local
  derived or adapter-only fields.
- No current sprint artifact relies on graph or UI surfaces to define the
  contract.
- `B1` can proceed knowing which product-level surfaces must remain canonical.

## Risks
- Risk: the shared contract becomes a union of convenience fields rather than a
  stable substrate.
  Mitigation: keep only fields all adopter lanes can own honestly at the
  top-level; move the rest into lane-local derived payloads.
- Risk: UI/workbench payloads reassert themselves as the practical truth layer.
  Mitigation: explicitly document them as consumers and reject UI-owned
  contract definitions in this sprint.
- Risk: Nat/Wikidata semantics try to redefine the shared compiler shape.
  Mitigation: keep adopter semantics below the frozen top-level contract and
  treat migration/revision specifics as lane-local payload meaning.

# Next Sprint: B1 — Shared Semantic Surface Definitions

## Goal
Define the canonical shared semantic owners for `text_surface`,
`candidate_surface`, `claim_surface`, `hint_surface`, and `decision_surface`
so affidavit, AU, GWB, and Wikidata/Nat stop treating lane-local facade files
as the truth layer for shared concepts.

## Why this sprint follows A1
- `A1` freezes the top-level compiler contract; `B1` freezes the shared meaning
  surfaces that live beneath that contract.
- `A2` and `A3` should normalize against shared semantic owners rather than
  growing AU-only or GWB-only wrappers around common concepts.
- `B2-B3` need a clean canonical substrate before proving-lane adoption can
  demonstrate real reuse instead of adapter coincidence.

## Scope
- In scope:
  - define canonical ownership for `text_surface`, `candidate_surface`,
    `claim_surface`, `hint_surface`, and `decision_surface`
  - distinguish shared semantic fields from lane-local adapters or convenience
    payloads
  - document which existing affidavit/AU/GWB/Wikidata-Nat wrappers become
    adapters versus true shared owners
  - specify cross-lane invariants for each shared surface
- Out of scope:
  - mass renames or broad mechanical call-site churn
  - proving-lane adoption beyond identifying the preferred `B2` and `B3`
    targets
  - UI/workbench-driven redefinitions of semantic ownership
  - adapter cleanup that should wait for `B4`

## Deliverables
- A shared semantic surface registry that names for each surface:
  - canonical owner/module
  - required fields and invariants
  - permitted adapter-local extensions
  - known current lane-local facades that should demote into adapters
- A lane impact table covering affidavit, AU, GWB, and Wikidata/Nat showing:
  - current wrapper/type owner
  - target shared owner
  - expected adapter boundary
  - blocking semantic mismatches to resolve in `B2-B3`
- A doctrine note stating that these shared surfaces are the semantic substrate
  beneath the compiler contract, while lane-local facades and UI payloads are
  derived or adapter-owned views

## Implementation checklist
1. Inventory current owners and wrapper files for `text_surface`,
   `candidate_surface`, `claim_surface`, `hint_surface`, and
   `decision_surface` across affidavit, AU, GWB, and Wikidata/Nat.
2. Separate true shared semantics from lane-local workflow affordances,
   presentation helpers, or provenance extras.
3. Write canonical field sets and invariants for each shared surface with
   explicit notes on what stays adapter-local.
4. Mark the preferred first adopter path for `B2` and the second adopter path
   for `B3` so proving-lane work starts from pre-declared shared owners.
5. Record which existing facade files should remain temporary adapters pending
   `B4` cleanup.

## Exit criteria
- Each named shared surface has one explicit canonical owner and documented
  invariants.
- The docs clearly distinguish shared surface ownership from lane-local facade
  wrappers and consumer-specific views.
- `A2` and `A3` can proceed without inventing new AU/GWB-local semantic truth
  layers for already-shared concepts.
- `B2-B3` can begin with a declared proving target instead of debating surface
  ownership from scratch.

## Risks
- Risk: affidavit-specific semantics get mistaken for cross-lane shared
  semantics.
  Mitigation: require at least one non-affidavit plausibility check per shared
  surface before calling it canonical.
- Risk: convenience wrappers survive as de facto substrate owners.
  Mitigation: explicitly label wrapper files as adapters when they are not the
  canonical owner.
- Risk: semantic fields are overfit to one adopter lane and fail during
  `B2-B3`.
  Mitigation: keep the canonical field set minimal and push optional
  lane-specific detail below the adapter boundary.

# Next Sprint: A2 — AU Normalization

## Goal
Normalize AU outputs around the frozen shared compiler spine and shared
semantic surface owners so AU fact-review and related handoff products stop
carrying AU-local top-level shape drift or AU-owned truth-layer wrappers for
already-shared concepts.

## Why this sprint follows B1
- `A1` fixes the top-level compiler contract and `B1` fixes the shared semantic
  substrate that AU should consume.
- AU is the safest first adopter because it already approximates the target
  compiler flow and can prove the architecture on a non-affidavit lane before
  GWB and Nat widen adoption.
- `A3` should inherit lessons from AU normalization rather than re-solving
  contract ownership independently.

## Scope
- In scope:
  - map AU fact-review/public handoff outputs to the shared compiler contract
  - align AU semantic payloads to shared `text_surface`,
    `candidate_surface`, `claim_surface`, `hint_surface`, and
    `decision_surface` owners where applicable
  - document AU-specific extensions that remain honest lane-local payloads
  - identify any AU adapters required to bridge current emitters to the shared
    contract
- Out of scope:
  - GWB normalization work that belongs in `A3`
  - Nat/Wikidata adoption work that belongs in `A4`
  - shared gate hardening that belongs in `A5`
  - operator UX or workbench widening

## Deliverables
- An AU normalization mapping showing:
  - current AU producer entrypoints
  - current emitted payload shapes
  - target shared compiler and semantic surface mappings
  - remaining AU-local fields that stay below the shared boundary
- An AU doctrine note defining:
  - which AU payloads are canonical shared outputs
  - which AU payloads are derived views or adapters
  - which semantics remain AU-specific and why
- A sprint-ready delta list for `A3` showing which AU issues were general
  normalization lessons versus AU-only edge cases

## Implementation checklist
1. Inventory AU producer/runtime seams that emit fact-review bundles, promoted
   outcomes, and downstream derived products.
2. Map each AU payload to the shared compiler contract and mark any missing or
   overgrown fields.
3. Align AU semantic structures to the `B1` shared surface owners and isolate
   AU-only workflow or provenance helpers behind adapter boundaries.
4. Record honest AU-local extensions separately from shared contract fields so
   they do not backflow into the substrate.
5. Produce a narrow handoff list for `A3` describing what GWB can reuse from
   AU normalization without inheriting AU-specific quirks.

## Exit criteria
- AU has an explicit documented mapping to the shared compiler contract.
- AU shared-concept payloads point at the `B1` semantic owners rather than
  AU-local truth-layer wrappers.
- AU-specific semantics are clearly documented as lane-local extensions or
  derived views.
- `A3` can start from a proven non-affidavit normalization example instead of
  reopening the shared contract debate.

## Risks
- Risk: AU convenience payloads get promoted into shared contract fields
  because they are already present.
  Mitigation: require each top-level shared field to justify cross-lane reuse,
  not just AU availability.
- Risk: AU provenance or review helpers leak back into shared semantic owners.
  Mitigation: keep workflow and review affordances adapter-local unless another
  lane can own them honestly.
- Risk: AU normalization quietly depends on operator/read-model assumptions.
  Mitigation: reject any AU mapping that needs UI/workbench semantics to remain
  intelligible.

# Next Sprint: A3 — GWB Normalization

## Goal
Normalize GWB outputs around the same shared compiler spine and shared semantic
surface owners so public review and broader review products stop depending on
GWB-local top-level contract drift or GWB-owned wrappers for already-shared
cross-lane concepts.

## Why this sprint follows A2
- `A2` provides the first non-affidavit normalization pass against the shared
  compiler and semantic substrate.
- `A3` should reuse the proven AU lessons where they generalize, while keeping
  GWB-specific review semantics adapter-local rather than redefining the shared
  layer.
- `B2-B3` need a second concrete non-affidavit adopter path that shows the
  architecture holds beyond AU.

## Scope
- In scope:
  - map GWB public handoff, public review, and broader review outputs to the
    shared compiler contract
  - align GWB semantic payloads to shared `text_surface`,
    `candidate_surface`, `claim_surface`, `hint_surface`, and
    `decision_surface` owners where applicable
  - document which GWB review semantics stay lane-local and why
  - identify any GWB adapters required to bridge current emitters to the shared
    contract
- Out of scope:
  - proving-lane adoption work that belongs in `B2-B3`
  - Nat/Wikidata adoption work that belongs in `A4`
  - shared gate hardening that belongs in `A5`
  - operator UX or workbench widening

## Deliverables
- A GWB normalization mapping showing:
  - current GWB producer entrypoints
  - current emitted payload shapes
  - target shared compiler and semantic surface mappings
  - remaining GWB-local fields that stay below the shared boundary
- A GWB doctrine note defining:
  - which GWB payloads are canonical shared outputs
  - which GWB payloads are derived views or adapters
  - which semantics remain GWB-specific and why
- A proving-lane handoff note for `B2-B3` showing:
  - what GWB successfully adopted from the shared substrate
  - what required GWB-only adapters
  - which shared surface candidates are now strongest for wider adoption

## Implementation checklist
1. Inventory GWB producer/runtime seams that emit public review, broader
   review, promoted outcomes, and downstream derived products.
2. Map each GWB payload to the shared compiler contract and mark any missing or
   overgrown fields.
3. Align GWB semantic structures to the `B1` shared surface owners and isolate
   GWB-only workflow or review helpers behind adapter boundaries.
4. Reuse `A2` lessons where they are genuinely cross-lane, while recording
   where GWB semantics diverge and must remain lane-local.
5. Produce a narrow handoff list for `B2-B3` describing which shared surfaces
   now have credible multi-lane adoption evidence.

## Exit criteria
- GWB has an explicit documented mapping to the shared compiler contract.
- GWB shared-concept payloads point at the `B1` semantic owners rather than
  GWB-local truth-layer wrappers.
- GWB-specific review semantics are clearly documented as lane-local
  extensions or derived views.
- `B2-B3` can begin from two concrete non-affidavit normalization examples
  instead of inferring cross-lane reuse from AU alone.

## Risks
- Risk: GWB broader-review affordances get mistaken for shared compiler or
  semantic contract requirements.
  Mitigation: require explicit cross-lane justification before promoting any
  GWB review field into a shared owner.
- Risk: AU normalization shortcuts get copied into GWB even where the review
  model differs.
  Mitigation: reuse `A2` only as precedent for ownership discipline, not as a
  template for GWB-specific semantics.
- Risk: GWB keeps consumer-oriented payloads as de facto truth-layer outputs.
  Mitigation: keep read-model and workbench shaping downstream of the
  normalized compiler contract.

# Next Sprint: B2 — First Proving-Lane Adoption

## Goal
Prove that at least one shared semantic surface can be adopted honestly by
affidavit and one non-affidavit lane without spawning a second lane-specific
truth-layer type for the same concept.

## Why this sprint follows A3
- `A1`, `B1`, `A2`, and `A3` establish the shared compiler spine, the shared
  semantic owners, and two concrete non-affidavit normalization examples.
- `B2` is the first point where the repo has enough substrate stability to
  prove that a shared surface is genuinely reusable rather than merely named
  consistently.
- `B3` should widen an already-proven pattern, not debate whether the first
  proving cut was valid.

## Scope
- In scope:
  - choose the strongest first proving target among `text_surface`,
    `candidate_surface`, `claim_surface`, `hint_surface`, and
    `decision_surface`
  - land one honest shared-surface adoption across affidavit and one
    non-affidavit lane, with AU as the default preferred adopter if the fit
    remains strongest
  - document the adapter boundary required to preserve lane-local semantics
    without cloning the shared owner
  - record acceptance evidence showing the shared type survives real lane
    differences
- Out of scope:
  - second non-affidavit adoption work that belongs in `B3`
  - Nat/Wikidata compiler adoption work that belongs in `A4`
  - shared gate hardening that belongs in `A5`
  - operator UX or workbench widening

## Deliverables
- A first proving-lane adoption note showing:
  - selected shared surface target
  - canonical owner being adopted
  - participating lanes and adapter boundaries
  - evidence that no second truth-layer type was introduced
- A cross-lane evidence table covering affidavit and the first non-affidavit
  adopter with:
  - current call sites or payload touchpoints
  - shared fields used directly
  - lane-local extensions kept below the adapter boundary
  - unresolved mismatches deferred to `B3` or `B4`
- A doctrine note defining the proof standard for calling a shared surface
  genuinely cross-lane rather than merely alias-compatible

## Implementation checklist
1. Select the most credible `B2` proving target from the `B1` registry based
   on lowest semantic distortion across affidavit and one non-affidavit lane.
2. Trace the current affidavit owner and the chosen adopter-lane owner for
   that surface and mark where wrappers can become adapters.
3. Define the exact shared field usage, invariants, and lane-local extension
   boundary for the proving cut.
4. Record concrete evidence that the adopter lane uses the canonical shared
   owner rather than a renamed clone or facade shell.
5. Produce a tight handoff for `B3` describing what remains to prove the
   surface is stable across a second non-affidavit lane.

## Exit criteria
- One shared semantic surface is explicitly adopted by affidavit and one
  non-affidavit lane.
- The adoption uses the `B1` canonical owner directly rather than introducing a
  second lane-specific truth-layer type for the same concept.
- Lane-local workflow or provenance semantics remain adapter-local and do not
  backflow into the shared owner.
- `B3` can widen from a concrete proof artifact instead of restarting the
  ownership discussion.

## Risks
- Risk: the chosen proving target only appears reusable because its semantics
  were hollowed out too far.
  Mitigation: require the proving surface to remain meaningful in both lanes,
  not merely structurally compatible.
- Risk: affidavit assumptions quietly dominate the shared owner.
  Mitigation: treat the non-affidavit adopter as an equal validity check and
  reject fields that only affidavit can own honestly.
- Risk: adapter wrappers get relabeled as proof of reuse without true canonical
  owner adoption.
  Mitigation: demand explicit evidence that downstream lane code touches the
  shared owner itself, with wrappers documented as adapters only.

# Sprint: S6 — Normative Reasoning Surfaces (Non-Judgmental)

## Goal
Expose queryable, explainable, and composable views over the frozen S4–S5 normative lattice **without** adding legal reasoning, compliance judgements, ontologies, or ML. Outputs must remain read-only, deterministic, and identity-neutral.

## Scope
- Read-only query helpers across actor/action/object/scope/lifecycle metadata.
- Explanation/trace payloads that map atoms back to clause IDs and text spans.
- Cross-version obligation alignment reports (unchanged/modified/added/removed with metadata deltas).
- Deterministic view projections (actor-centric, action-centric, timeline, clause-grouped).
- Versioned JSON schemas for obligation, explanation, diff, and graph payloads.
- No-reasoning guardrails and red-flag tests to freeze the descriptive-only contract.

## Constraints
- Clause-local, text-derived only; no ontology lookup, inference, or compliance evaluation.
- Identity/diff invariants (CR-ID, OBL-ID) remain frozen; new surfaces must not alter identities.
- Deterministic ordering for all emitted collections; formatting/OCR noise must not change results.
- Feature flags remain available; new surfaces should respect actor/action binding toggles.

## Deliverables
- S6.1 Query API (read-only filters; flag-respecting).
- S6.2 Explanation surfaces (deterministic atom→span mapping).
- S6.3 Cross-version alignment report with metadata deltas.
- S6.4 Normative view projection builders (actor/action/timeline/clause).
- S6.5 Versioned JSON schemas (obligation, explanation, diff, graph) with backward-compat parsing tests.
- S6.6 Hard-stop guard doc + red-flag tests to prevent reasoning/ontology creep.

## Plan (sequencing)
1) S6.1 Query API → validate payload fidelity without touching identity.
2) S6.2 Explanations → make outputs auditable and stable.
3) S6.3 Alignment → human-readable change summaries atop identity diff.
4) S6.4 View projections → deterministic alternate lenses on the same graph.
5) S6.5 External contracts → freeze schemas for downstream consumers.
6) S6.6 Gate review → enforce “descriptive-only” boundary with tests/docs.

## Acceptance Criteria
- Queries and explanations are deterministic under formatting/OCR/numbering changes and respect actor/action flags.
- Alignment reports show metadata deltas without breaking unchanged identities.
- View projections produce reproducible outputs; no invented nodes or edges.
- Schemas are versioned and backward-compatible; round-trip tests pass.
- Red-flag tests fail if compliance reasoning, ontology expansion, or inference is introduced.
- Full regression suite remains green.

## Risks / Mitigations
- Risk: accidental reasoning creep → Mitigation: red-flag tests and explicit guard doc.
- Risk: schema churn → Mitigation: versioned schemas with backward-compat harness.
- Risk: nondeterministic ordering → Mitigation: stable sort keys across all surfaces.
- Risk: flag bypass → Mitigation: unit tests for actor/action flag interactions on query/explanation outputs.
