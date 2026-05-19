# Wikidata OCTF Entrypoint

Date: 2026-04-21

## Purpose

Give the Wikidata Ontology Cleaning Task Force one practical entry point into
the current work.

This note is for reviewers who want to know what the repo can check, what a
reviewer sees, and where human judgment is still required.

If you want a start-to-finish command guide for the documented Wikidata stories,
start with:

- `SensibLaw/docs/wikidata/README.md`

This note is still useful when you want to know:

- where to start
- what is runnable
- what can be checked
- what should not be inferred
- how adjacent Wikibase/Wikidata sync tools can feed the review layer without
  becoming edit authority

## Who this is for

| Reader | Primary need | Start here |
| --- | --- | --- |
| Dave / general OCTF | Plain-language overview, worked example, what a reviewer sees | Short version -> Worked example |
| Peter | Ontology-support tooling, `P2738` disjointness, review-first boundary | Short version -> Parallel review lanes -> Bounded disjointness diagnostics |
| Ege | `P2738` / `P11260` pairwise extraction, violation counts, bounded disjointness reports | Parallel review lanes -> Bounded disjointness diagnostics -> Programmatic entry points |
| Rosario | Hotspot packs, benchmark/scorer framing, cross-domain examples | Parallel review lanes -> Structural hotspot packs -> Programmatic entry points |

## Short version

The practical problem is that Wikidata ontology-related properties can express
constraints or review pressure faster than the available tooling can check
them. Without bounded checks, violations and uncertain cases accumulate, and
reviewers have to reconstruct too much context by hand.

The repo's current role is to gather a small relevant part of the graph, compare
candidate changes against local evidence and qualifiers, and produce review
reports before anything is staged. It is a review/check layer, not an approval
layer and not a blind edit bot.

Adjacent Wikibase/Wikidata sync tools can sit before or after this layer. For
example, Claire/Superraptor's `Wikibase-Wikidata-Pipeline` can map a local
Wikibase to Wikidata, detect missing statements or missing references, and use
`WikibaseIntegrator` as an upload path. That is useful transport/edit tooling.
The OCTF-relevant ITIR/SensibLaw role is different: convert those candidate
deltas into bounded review packets, preserve provenance, check structural and
reference pressure, and emit dispositions before any staging/export step.

Tool findings can come from:

- subclass or instance checks
- disjointness checks
- constraint checks
- LLM suggestions
- external scaffolds such as DBpedia or SUMO
- external Wikibase/Wikidata delta tools such as `Wikibase-Wikidata-Pipeline`

The repo should not treat those findings as edit authority. The working pattern
is still:

1. materialize a bounded slice
2. classify it into explicit buckets
3. expose a reviewer-facing report or pack
4. stage only the checked-safe subset
5. verify after any edit

## What this is not

- This is not an automatic edit bot.
- This is not a replacement for community review.
- This is not a claim that DBpedia, SUMO, or LLM output can impose constraints.
- This is not a claim that the repo solves Wikidata ontology correctness.
- This is not an approval workflow.
- This is not a replacement for Wikibase/Wikidata transport tools or local
  Wikibase setup tools.
- This is not a claim that an external sync/upload script has passed
  admissibility review just because it found a missing statement.

The narrower claim is:

- tool findings become bounded review artifacts first
- only locally complete, checked-safe rows are staged
- uncertain rows remain visibly uncertain

## Worked example

A `P5991` climate row may look like it belongs on `P14143`, but the tool still
checks whether the row has the right time qualifier, scope, method, value, and
references. If the row has annual organization-level emissions with the needed
qualifiers and references, it can become checked-safe for staging. If it mixes
several years, scopes, methods, or values, it stays held or becomes a split
review case.

What the reviewer sees is not "edit this." The reviewer sees a bounded packet
with a disposition such as:

- safe to stage
- split first
- incomplete
- held for ontology or evidence review

## Generalized progress since this handoff

Since the April 21 handoff, the repo has not become a Wikidata edit bot and it
has not gained authority to decide ontology policy. What changed is that the
review packets are clearer: tool findings are kept as candidate evidence,
reports show why a row is safe, incomplete, contradictory, or held, and only
locally complete checked-safe rows move to the next governed staging step.

There is a sharper formal/runtime split behind that practical statement. The
latest formalism is broader than the current bounded product mode: it describes
a monotone structural-coherence framework over a snapshot-derived global
ontology index.

Formal endstate:

```text
global ontology snapshot Omega
-> compile statements and constraints into typed carriers
-> compute residual/severity per item or slice
-> generate candidate mutations
-> admit only mutations where severity(after) <= severity(before)
-> aggregate structural incoherence cannot increase
-> the finite lattice reaches a fixed point
```

In that reading, a bounded review packet is the local projection of a global
latent structural state. A completed QID-only tool could take `Q27968055`,
project the relevant slice from the global index, identify inheritance pressure
through paths such as `Q3331189` and `Q1656682`, check class-order and
disjointness surfaces, and emit candidate local or upstream mutations that do
not worsen structural coherence.

External sync tools remain outside that formal authority boundary. Their
detected deltas are useful candidate mutations, but the coherence/admissibility
claim begins only after the delta is normalized into a bounded packet and
checked by the review layer.

The current runtime is not yet that full product. The implemented Wikidata
surface is made of bounded lanes: migration packs, PNF/residual climate review
packets, hotspot packs, disjointness reports, grounding/live-follow review
surfaces, and a first `ChangeReviewPacket` harness that compares
expert-supplied ontology repair candidates on an in-memory bounded slice. That
harness can now also emit review-only pressure attribution buckets for local,
upstream, sibling, downstream, temporal/mereology, metaclass-order, and
disjointness pressure. These instantiate pieces of the formalism, but they do
not yet materialize a full global ontology index or automatically rank
arbitrary ontology repairs from a QID alone.

The roadmap should therefore be read in layers:

1. bounded v0: reviewer supplies QID or task plus candidate repairs; the app
   compares and emits review dispositions. The current executable surface is
   `wikidata compare-candidates` over
   `tests/fixtures/wikidata/q27968055_change_review_packet.json`.
2. QID-only bot: reviewer supplies only the QID; the app diagnoses pressure and
   emits locally coherence-improving candidates
3. global ontology index: snapshot-derived `Omega` with `P279` closure,
   `P2738`/`P11260` disjointness closure, constraint signatures, upstream
   references, and class-order/metaclass surfaces
4. global latent coherence field: every item has residual/severity/pressure
   state against that index
5. monotone coherence bot: generated mutations are emitted only when
   `severity(after) <= severity(before)`
6. filter-respecting edit stream: if applied edits all carry passing receipts,
   aggregate structural incoherence cannot increase
7. governance boundary: the bot certifies structural-coherence improvement;
   the Wikidata community still certifies edit desirability

## What the newer PNF/body work adds

For reviewers, the practical change is that the output can distinguish more
clearly between "this is missing required evidence" and "this conflicts with
local evidence." That is useful because incomplete cases should be repaired or
held, while contradictory cases need a different review conversation.

The stronger claim is still not "the Wikidata lane is now automated."

For technical readers, the narrower claim is:

- the canonical substrate is getting stricter
- the candidate layer is getting more explicit
- the comparison/gating layer is getting more deterministic

In current code and planning docs this shows up as:

- canonical text and media-adapter discipline above parsing
- explicit predicate-normal-form carriers separating:
  - structure
  - typed roles
  - qualifiers
  - wrapper/evidence-only state
- a deterministic residual lattice with ordered outcomes such as:
  - `exact`
  - `partial`
  - `no_typed_meet`
  - `contradiction`

That matters for OCTF because it sharpens the same boundary this note is
already describing:

- LLM suggestions remain candidate signals
- subclass/disjointness/constraint signals remain candidate signals
- even a correct signal may still be partial, scope-mismatched, or
  locally incomplete
- the decision boundary is therefore not "did a signal fire?"
- the decision boundary is "did a bounded artifact expose enough typed structure
  and residual state to be reviewable, held, or promotable?"

So the current repo stance is slightly stronger than a generic "human in the
loop" claim:

- signals are non-authoritative intermediate state
- bounded packs/reports are the review surface
- only checked-safe, locally complete rows are staged
- unresolved rows remain visibly unresolved

Plain-language translation:

- `graph slice` means the small relevant part of the graph.
- `signal` means a tool finding or evidence pointer.
- `candidate-only` means not ready to edit.
- `reviewable` means ready for inspection.
- `held` means needs review or repair.
- `promotable` means safe to stage under the current local rules.
- `residual lattice` means the deterministic final check result.

## Best first path

Start with the climate migration lane because it has the clearest end-to-end
artifact:

- source property: `P5991` (`carbon footprint`)
- target property: `P14143` (`annual greenhouse gas emissions`)
- pilot pack:
  `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`

Read these first:

1. `SensibLaw/docs/wikidata_working_group_status.md`
2. `SensibLaw/docs/planning/wikidata_migration_pack_contract_20260328.md`
3. `SensibLaw/docs/planning/wikidata_ontology_group_handoff_nat_lane_20260401.md`

If you want the simplest plain-language handoff, read:

- `SensibLaw/docs/planning/wikidata_shixiong_handoff_20260402.md`

That file is named for a specific collaborator, but it is currently the shortest
plain-language overview of the migration/review lane.

If you want one concrete note showing how a real Wikidata climate case should
be read through the newer canonical-text / PNF / residual framing, read:

- `SensibLaw/docs/planning/wikidata_pnf_residual_review_example_20260429.md`

## Adjacent Reference Repos

Two external Claire/Superraptor repositories are relevant references for OCTF
discussions because they cover practical transport surfaces around the bounded
review layer:

- `https://github.com/Superraptor/Wikibase-Wikidata-Pipeline`
  - maps local Wikibase entities/properties to Wikidata IDs
  - detects missing statements and missing references across the mapping
  - contains a `WikibaseIntegrator` upload path
  - useful to us as an upstream candidate-delta source or downstream reviewed
    upload adapter
- `https://github.com/Superraptor/wikiodk`
  - proof-of-concept ODK/TTL to local Wikibase setup and import path
  - useful as a sandbox/local-Wikibase reference surface when ontology-shaped
    inputs need to be loaded before sync/review

The collaboration boundary is:

```text
external Wikibase/Wikidata delta
-> bounded ITIR/SensibLaw review packet
-> structural/provenance/admissibility diagnostics
-> disposition: checked-safe, held, contradictory, or insufficiently supported
-> optional reviewed export back to an upload/staging path
```

This is the clean OCTF message: transport tools can find and move candidate
statements; the ITIR/SensibLaw layer decides whether the candidate has enough
bounded evidence and structural coherence to be reviewable or staged.

## Programmatic entry points

This section is for technical contributors who want to run the local commands.
Non-technical reviewers can skip to "OCTF-facing vocabulary" or "Parallel
review lanes."

The main CLI entry points are under the Wikidata command group.

Local repo invocation used in the existing docs:

```bash
cd SensibLaw
../.venv/bin/pip install -e .[dev,test]
../.venv/bin/python -m cli.__main__ wikidata --help
```

Climate migration pack:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata build-migration-pack \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/slice.json \
  --source-property P5991 \
  --target-property P14143 \
  --output /tmp/p5991_p14143_migration_pack.json
```

OpenRefine review export:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata export-migration-pack-openrefine \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --output /tmp/p5991_p14143_openrefine.csv
```

Checked-safe-only export:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata export-migration-pack-checked-safe \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --output /tmp/p5991_p14143_checked_safe.csv
```

Post-edit verification:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata verify-migration-pack \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --after path/to/after_state_slice.json \
  --output /tmp/p5991_p14143_verification.json
```

Split-plan review surface:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata build-split-plan \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --output /tmp/p5991_p14143_split_plan.json
```

Cross-lane governance summary:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata world-model-lane-summary \
  --input path/to/lane_report_1.json \
  --input path/to/lane_report_2.json \
  --output /tmp/wikidata_world_model_lane_summary.json
```

This is not a replacement for the bounded migration/disjointness/hotspot
surfaces above. It is the current shared summary surface when a reviewer wants
one governance-oriented view across multiple lane reports.

## OCTF-facing vocabulary

The current repo vocabulary that maps most cleanly to OCTF review work is:

- `candidate-only`
  - a signal or structured candidate exists, but it is not an edit claim
  - plain language: not ready to edit
- `reviewable`
  - the bounded artifact exposes enough local structure and provenance for
    human inspection
  - plain language: ready for inspection
- `held`
  - the case stays visible, but it is not ready for direct migration/promotion
  - plain language: needs review or repair
- `promotable`
  - the artifact has passed its local gate and can move to the next governed
    step
  - plain language: safe to stage under the current local rules

For Wikidata specifically, this means a useful tool should not only say "there
may be a problem here." It should also say whether the case is still merely a
candidate, is concretely reviewable, should stay held, or is promotable under
the current bounded rules.

## Parallel review lanes

The same review-first pattern also exists in two structural ontology lanes.

Structural hotspot packs:

These produce bounded clusters of related ontology questions so reviewers can
inspect a neighborhood of possible class/order problems instead of chasing one
isolated item at a time.

- docs:
  `docs/planning/wikidata_hotspot_pack_contract_20260325.md`
- manifest:
  `docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json`
- invocation note:
  run this command from the repo root because manifest source artifacts are
  root-relative
- CLI:

```bash
PYTHONPATH=SensibLaw .venv/bin/python -m cli.__main__ wikidata hotspot-generate-clusters \
  --manifest docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json \
  --output /tmp/wikidata_hotspot_clusters.json
```

Bounded disjointness diagnostics:

These produce a report of subclass and instance-level pressure around
`disjoint union of` (`P2738`) inside a named slice. The output is meant to show
where review is needed, not to revert edits or impose a new ontology rule.
The command materializes the pairwise disjoint-class surface from the `P11260`
qualifiers carried by the bounded `P2738` statements.

- docs:
  `docs/planning/wikidata_disjointness_report_contract_v1_20260325.md`
- case index:
  `docs/planning/wikidata_disjointness_case_index_v1.json`
- CLI:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata disjointness-report \
  --input path/to/bounded_disjointness_slice.json \
  --output /tmp/wikidata_disjointness_report.json
```

## Current review question

The useful question for OCTF is not whether every candidate signal should become
an edit.

The useful question is:

- does this bounded report or pack expose enough information for a reviewer to
  decide whether the case is safe, split-required, repair-needed, held, or
  reconstruct-only?

For the climate lane, the current routing boundary is:

- annual organization-level emissions can route toward `P14143`
- product or lifecycle carbon footprint stays on `P5991`
- emissions intensity, avoided emissions, offsets, and removals stay held until
  a specific target property is confirmed
- non-emissions metrics are blocked

## Final boundary

Do not upgrade this note into a claim of full Wikidata automation, full ontology
correctness, or parity with broader ontology-cleaning work. The supported claim
is narrower: deterministic, review-first intermediate artifacts with bounded
residual states and no hidden edit authority.
