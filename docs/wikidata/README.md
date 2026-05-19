# Wikidata Review Guide

Date: 2026-05-05

This is the practical start-to-finish guide for the current Wikidata docs. It
assumes the repo environment is already installed.

The important boundary is simple: these tools prepare bounded review artifacts.
They do not approve edits, run an edit bot, or turn LLM, DBpedia, SUMO, subclass,
constraint, or disjointness signals into authority by themselves.

## Who This Is For

| Reader | Primary need | Start here |
| --- | --- | --- |
| Dave / general OCTF | Plain-language overview, worked example, what a reviewer sees | `../planning/wikidata_octf_entrypoint_20260421.md` -> Story 1 |
| Peter | Ontology-support tooling, `P2738` disjointness, review-first boundary | Story 4 -> `../planning/wikidata_octf_entrypoint_20260421.md` |
| Ege | `P2738` / `P11260` pairwise extraction, violation counts, bounded disjointness reports | Story 4 |
| Rosario | Hotspot packs, benchmark/scorer framing, cross-domain examples | Story 3 |

## Command Convention

The package defines a `sensiblaw` console script in `pyproject.toml`. That
script exists only after the package has been installed into the environment.

Installed form:

```bash
cd SensibLaw
../.venv/bin/pip install -e .
../.venv/bin/sensiblaw wikidata --help
```

Checkout fallback form, which works even when the console script is not present:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata --help
```

The commands below use the fallback form to avoid assuming the `sensiblaw`
script has been installed.

The hotspot manifest is the exception because its source artifacts are
repo-root-relative. That story is run from the repo root with
`PYTHONPATH=SensibLaw`.

Most examples write to `/tmp` so they do not disturb checked-in fixtures.

## How The Pieces Fit

For the Wikidata migration lane, the repo does not start by inventing a global
ontology recommendation. It starts with a bounded proposal, such as "review
whether `P5991` rows can become `P14143` rows," and turns that proposal into a
review packet.

That sentence describes the current runnable product mode, not the full
formalism. The latest ITIR/SensibLaw formalism is broader: it treats bounded
review packets as local projections of a possible snapshot-derived global
ontology index. In that endstate, a global snapshot `Omega` is compiled into
typed statement, constraint, disjointness, class-order, upstream-reference, and
residual/severity carriers. Candidate mutations are admitted only when they
pass a monotone coherence filter:

```text
severity(after) <= severity(before)
```

Under a finite residual lattice and a filter-respecting edit stream, aggregate
structural incoherence cannot increase and eventually reaches a fixed point.
That is a structural-coherence certification claim, not Wikidata edit
authority. Community review still decides whether a structurally admissible
candidate is desirable.

The current repo is not yet that full QID-only/global-index bot. The practical
guide below documents the implemented bounded lanes: migration packs,
PNF/residual climate review packets, structural hotspot packs, bounded `P2738`
disjointness diagnostics, and a first review-only `ChangeReviewPacket` harness
for comparing expert-supplied ontology repair candidates on one bounded slice.
A future QID-only lane would let a reviewer provide only a focus item, have the
system compute pressure against the global index, and emit locally
coherence-improving candidate mutations for review.

The practical flow is:

1. Choose a bounded task, property pair, or hotspot family.
2. Materialize source data as revision-locked JSON.
3. Build `slice.json`, which contains the relevant statement bundles grouped
   into named windows.
4. Run a Python builder such as `wikidata build-migration-pack`.
5. Emit `migration_pack.json`, which classifies each candidate row.
6. Export only review surfaces or checked-safe staging rows.
7. Keep held, incomplete, split-required, or contradictory rows out of direct
   execution.

In this lane, a "recommendation" means the row-level disposition in the review
packet, for example `migrate`, `split`, `review`, or `abstain`. It is a
deterministic review aid, not Wikidata edit authority.

Key file roles:

| File or object | Role |
| --- | --- |
| `manifest.json` | Inventory and provenance file. It records which QIDs, revisions, source exports, `slice.json`, and generated pack belong together. |
| `slice.json` | Bounded source data. It contains statement bundles grouped into windows such as `t1_previous` and `t2_current`. |
| `migration_pack.json` | Reviewer-facing result. It contains candidate rows, classifications, actions, reasons, diffs, gates, and summary counts. |
| `schemas/*.schema.yaml` | Machine-readable contract for a JSON payload. A schema says what fields and value shapes are allowed. |
| `src/ontology/wikidata.py` | Manually written deterministic builders, classifiers, exporters, and verifiers for Wikidata review artifacts. |
| `src/ontology/wikidata_change_review.py` | Review-only candidate comparison harness. It mutates bounded slices in memory, runs deterministic diagnostics, and emits candidate dispositions without edit authority. |
| `cli/__main__.py` | Manually written command-line wiring. It exposes the Python functions as `wikidata ...` subcommands. |

In this document, a window is a named snapshot inside the bounded slice. For
the migration pack, the current window is the last window in the slice and the
previous window is the second-to-last window when present. The previous window
is used for drift checks; the current window is where candidate rows are
classified.

## Reviewer States

The docs use four operational states:

- `candidate-only`: a tool finding exists, but it is not ready to edit.
- `reviewable`: the report exposes enough local evidence for a human review.
- `held`: the case remains visible, but it is incomplete, ambiguous, or unsafe
  to stage.
- `promotable`: the local gate passed and the row can move to the next governed
  step.

Plain-language shorthand:

- `candidate-only` means not ready to edit.
- `reviewable` means ready for inspection.
- `held` means needs review or repair.
- `promotable` means safe to stage under the current local rules.

## Story 1: Climate Property Migration

Use this when reviewing whether `P5991` (`carbon footprint`) rows can become
`P14143` (`annual greenhouse gas emissions`) rows without losing qualifier or
reference semantics.

Start with the pinned pilot pack:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata build-migration-pack \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/slice.json \
  --source-property P5991 \
  --target-property P14143 \
  --output /tmp/p5991_p14143_migration_pack.json
```

Review all rows in a flat CSV:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata export-migration-pack-openrefine \
  --input /tmp/p5991_p14143_migration_pack.json \
  --output /tmp/p5991_p14143_openrefine.csv
```

Stage only locally checked-safe rows:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata export-migration-pack-checked-safe \
  --input /tmp/p5991_p14143_migration_pack.json \
  --output /tmp/p5991_p14143_checked_safe.csv
```

If rows need splitting, build the review-only split plan:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata build-split-plan \
  --input /tmp/p5991_p14143_migration_pack.json \
  --output /tmp/p5991_p14143_split_plan.json
```

After a sandbox or later governed edit path produces an after-state slice,
verify the checked-safe subset:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata verify-migration-pack \
  --input /tmp/p5991_p14143_migration_pack.json \
  --after path/to/after_state_slice.json \
  --output /tmp/p5991_p14143_verification.json
```

Finish when the reviewer has a migration pack, optional OpenRefine CSV, optional
checked-safe CSV, optional split plan, and verification report for any attempted
after-state. The checked-safe CSV is a staging artifact, not edit authority.

## Story 2: Climate PNF/Residual Review Packet

Use this when a reviewer needs one compact object showing how a concrete climate
case moves from candidate change to final held/promotable disposition.

Run the demonstrator over the pinned Akademiska Hus case:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata climate-review-demonstrator \
  --migration-pack data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --climate-text data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json \
  --review-packet tests/fixtures/wikidata/wikidata_nat_review_packet_20260401.json \
  --output /tmp/q10403939_climate_review_demonstrator.json
```

Finish when the output JSON shows:

- the bounded candidate change surface
- the text-side predicate carrier
- the residual/completeness surface
- the final review disposition

This story is the clearest bridge from the practical migration lane into the
predicate-normal-form and residual-gating language.

## Story 3: Structural Hotspot Packs

Use this when reviewing clusters of related ontology questions rather than one
property migration.

Generate all hotspot clusters from the current manifest:

```bash
PYTHONPATH=SensibLaw .venv/bin/python -m cli.__main__ wikidata hotspot-generate-clusters \
  --manifest docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json \
  --output /tmp/wikidata_hotspot_clusters.json
```

To focus on one pack:

```bash
PYTHONPATH=SensibLaw .venv/bin/python -m cli.__main__ wikidata hotspot-generate-clusters \
  --manifest docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json \
  --pack-id software_entity_kind_collapse_pack_v0 \
  --output /tmp/software_entity_kind_collapse_clusters.json
```

Finish when the cluster JSON gives the reviewer a bounded set of related
questions and source pack identifiers. The cluster pack is a review surface, not
a rewrite plan.

## Story 4: P2738 Disjointness Diagnostics

Use this when checking bounded violations around `disjoint union of` (`P2738`).
The report extracts the pairwise disjoint-class surface from `P11260`
qualifiers and then separates subclass and instance pressure inside the slice.

Run the report against the pilot fixture:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata disjointness-report \
  --input tests/fixtures/wikidata/disjointness_p2738_pilot_pack_v1/slice.json \
  --output /tmp/wikidata_disjointness_report.json
```

Other real bounded packs are also available under:

- `tests/fixtures/wikidata/disjointness_p2738_fixed_construction_real_pack_v1/`
- `tests/fixtures/wikidata/disjointness_p2738_working_fluid_real_pack_v1/`
- `tests/fixtures/wikidata/disjointness_p2738_nucleon_real_pack_v1/`

Finish when the report separates subclass and instance violations inside the
bounded slice. It identifies review pressure; it does not revert edits or impose
new ontology rules.

## Story 5: ChangeReviewPacket Candidate Comparison

Use this when a reviewer has a focus QID and a small approved candidate repair
space, such as keep, remove, weaken, retype, or hold options for an ontology
case. This is the current Level 0 executable slice of the broader
structural-coherence roadmap: the reviewer supplies or approves candidates, the
runtime applies each candidate to the bounded slice in memory, and the report
returns deterministic non-authoritative dispositions.

Run the synthetic `Q27968055` packet fixture:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata compare-candidates \
  --packet tests/fixtures/wikidata/q27968055_change_review_packet.json \
  --output /tmp/q27968055_change_review_report.json
```

The report includes:

- baseline diagnostics
- per-candidate diagnostics
- diagnostic deltas
- optional `pnf_index` report surface with dream-machine locator names:
  `receipt_index`, `predicate_pnf_index`, `structural_signature_index`,
  `constraint_pnf_index`, `shape_pnf_index`, `residual_index`,
  `pressure_index`, `candidate_index`, `mutation_pnf_index`,
  `disposition_index`, and `promotion_boundary`
- optional pressure-attribution buckets:
  `local`, `upstream`, `sibling`, `downstream`, `temporal_mereology`,
  `metaclass_order`, and `disjointness`
- check coverage for requested families, including deferred v0 families
- disposition counts
- `authority_policy: review_only`
- `edit_authority: false`

Current v0 dispositions are conservative:

- `checked_safe_reviewable`
- `held`
- `contradictory`
- `insufficiently_supported`

Packets may also name abstract obligation candidates:
`split_class_obligation`, `new_class_obligation`,
`new_property_obligation`, `relation_family_correction`,
`upstream_repair_obligation`, and `sibling_normalization_obligation`. These
are existential review objects only. They can record that a reviewer may need
to consider a class split, new class/property shape, relation-family correction,
upstream repair, or sibling normalization, but they are not real Wikidata
QIDs/PIDs, do not mint entities or properties, do not create PNF receipts, and
do not grant edit authority.

Finish when the report gives the reviewer a candidate comparison table and
enough evidence paths to decide what to inspect next. This story does not claim
live Wikidata authority, does not fabricate runtime receipts, and does not
prove global monotonicity by itself.

The pressure-attribution surface is only a review locator. `local` means the
candidate statement or directly bounded focus neighborhood carries the pressure;
`upstream` means an inherited class/property/reference dependency is implicated;
`sibling` means another candidate or peer statement in the bounded slice creates
the comparison pressure; `downstream` means consumers or dependent uses would
need review; `temporal_mereology` covers bounded parthood plus temporal-key
overlap or incompleteness; `metaclass_order` covers class/instance/metaclass
order pressure; and `disjointness` covers bounded `P2738`/`P11260` contradiction
pressure. None of these buckets is an instruction to edit Wikidata. They must
not be backed by fabricated PNF receipts, labels read by inspection, or a
monotonicity claim unless the input is a filter-respecting edit stream.

The `pnf_index` surface is also report-only. It may organize bounded evidence
paths under the dream-machine index names, but it must not invent receipts,
claim live Wikidata edit authority, promote candidates, or assert that an index
entry is true outside the supplied report inputs. `promotion_boundary` names the
review boundary only; it is not a promotion act.

Packets and reports may also carry an optional `pnf_grounding` or
`wikidata_grounding` surface for reviewer navigation from PredicatePNF to
candidate Wikidata rows. The only valid direction is
`PredicatePNF_to_Wikidata`: start from packet-supplied PredicatePNF carriers,
then list packet-supplied candidate QIDs, PIDs, or statement shapes for review.
The surface must not run in the reverse direction, infer new identifiers, mint
QIDs/PIDs, fabricate a `PNFEmissionReceipt`, or grant edit authority. It is a
review-only bridge over the candidate space already present in the
`ChangeReviewPacket`.

First-class family names are now reserved in the packet/report schemas for
`mereology` and `temporal_exclusivity`. The synthetic packet
`tests/fixtures/wikidata/change_review_mereology_temporal_packet.json`
shows the review-only shape for `P361`/`P527` mereology plus temporal-key
policy (`P580`, `P582`, `P585`). In v0.1 this is a representable request, not a
runtime authority claim: `compare-candidates` can report the families as run
when the packet's property scope covers the relevant parthood or temporal
exclusivity predicates. Treat any monotonicity read as filter-respecting and
bounded to the supplied slice.

## What To Read Next

- `../wikidata_working_group_status.md`: current Wikidata status and pointers.
- `../planning/wikidata_octf_entrypoint_20260421.md`: OCTF-facing overview.
- `../planning/wikidata_migration_pack_contract_20260328.md`: migration pack
  contract.
- `../planning/wikidata_pnf_residual_review_example_20260429.md`: concrete
  PNF/residual climate example.
- `../planning/wikidata_temporal_pnf_constraint_contract_20260502.md`: temporal
  constraint contract for climate and bounded mereology.
