# Wikidata Migration Pack Contract (2026-03-28)

Derived climate assessment note: the immutable company-direct replay may be
consumed by the offline, read-only orthogonal V2 assessment defined in
`climate_ghg_orthogonal_assessment_v2_20260717.md`. That derivation does not
change this migration-pack contract or grant edit/execution authority.

## Purpose
Define the first executable contract for a bounded property-migration review
artifact in the Wikidata lane.

This contract is intentionally operational and narrow:
- one source property
- one target property
- one bounded slice
- one current window basis
- reviewer-facing candidate rows

The initial anchor case remains:
- source property: `P5991`
- target property: `P14143`

## Status
Implemented in bounded `v0.1` form through:
- schema:
  - `schemas/sl.wikidata_migration_pack.v1.schema.yaml`
- runtime:
  - `src/ontology/wikidata.py`
- CLI:
  - `sensiblaw wikidata build-migration-pack`

`sensiblaw` is the installed console-script name from `pyproject.toml`. In a
plain checkout where that script has not been installed, use the module form
instead:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata build-migration-pack --help
```

## Bounded live discovery and reconciliation

Live discovery is a separate, statement-level intake step.  It is not a
property-renaming operation and it does not itself create a migration
candidate.  For the current climate profile the source property is broad
(`P5991`), whereas the target (`P14143`) is annual, entity-level greenhouse-gas
emissions.  A discovery page therefore records a typed stratum before any
classification is attempted.

The first live stratum is deliberately narrow:

```text
direct P31 company/business/enterprise
+ source P5991 statement
+ no existing target P14143 statement on the subject
```

Direct `P31` membership is only a bounded discovery filter.  It is not a
complete type closure and it does not by itself make a row migration-safe.
Subsequent strata may include bounded-superclass company membership, product,
person, event, non-enterprise organisation, unclear subject, and
already-targeted rows, each with their own review policy.

### Discovery manifest

Every live page must persist a deterministic discovery manifest before entity
retrieval.  The manifest contains:

- schema and query version plus query hash;
- endpoint, execution timestamp, deterministic ordering, page size, and
  cursor;
- source and target properties, selected subject-type stratum, and observed
  row count;
- per-row subject QID, source statement GUID, rank, direct P31 values, and
  whether the subject already has the target property;
- the raw WDQS response reference or content hash; and
- an explicit declaration that discovery has no promotion or edit authority.

### Revision-pinned reconciliation

Discovery and entity retrieval happen at different times.  For every row in a
bounded page, the materializer must retrieve a current revision-pinned entity
export and reconcile the discovered statement GUID against that export before
classification.  It records exactly one of:

```text
statement_reconciled
statement_changed_since_discovery
statement_missing
entity_revision_unavailable
```

Only `statement_reconciled` rows may enter the climate classifier.  The
classifier evaluates the complete statement family on that entity, rather than
only an isolated statement, so temporal/scope splits and target-property
coexistence remain visible.

### Resumable live replay transport

A wide discovery replay is a two-phase, read-only evidence operation:

```text
Phase A: discover every cursor page and pin the selected revision for each QID
Phase B: fetch or validate exactly those pinned entity exports
```

Before Phase B, the materializer writes an atomic `run-state.json` containing
the discovery/query contract hash, cursor bounds, population-exhaustion state,
ordered QIDs, and per-QID revision IDs/timestamps. A resume reuses that state
and never asks for a newer revision for an already pinned QID. Exports are
immutable `QID + revision` evidence files; an existing file is reused only
after its embedded QID/revision and content hash validate.

Alongside durable run state, the materializer writes atomic `progress.json`
after revision pinning and after each export. It exposes only operational
status: phase, total/completed/reused/downloaded export counts, current
QID/revision, elapsed time, throughput, estimated remaining time, and the
safe `--resume` command. It contains no credentials or contact identity. A
process may be stopped between updates and resumed from the pinned run state.
The same updates are emitted to stderr through the repository's shared terminal
progress callback: human, JSON-lines, or an interactive progress bar. Terminal
output covers both Phase A revision pinning and Phase B exports.

WDQS discovery, Action API revision lookup, and revision-pinned entity export
share one HTTP session and identity, but retain independent pacing and backoff
state. Each starts serially at a 500 ms interval. A `429` follows
`Retry-After`; missing retry guidance or a `503` uses bounded exponential
backoff with jitter for only the affected service. Non-interactive Action API
calls include `maxlag=5`.

The default User-Agent identifies the SensibLaw project URL. Operators may add
contact information and an OAuth token through process environment variables.
Contact identity is not authentication, and authentication's rate tier depends
on the account's standing. Tokens, contact values, and authorization headers
never enter state, receipts, manifests, or diagnostics.

Copy `.env.example` to a local ignored `.env`, set values there, and source it
in the invoking shell. The repository never writes a local `.env`. Wikimedia's
published current limits distinguish identified anonymous/new authenticated
clients from established authenticated editors; use a contact-bearing
User-Agent, serial requests, and the service response rather than treating a
token as a promise of a higher rate.

The resulting classifier input records the source statement GUID, quantity
unit, rank, `P585` time, `P459` method, `P3831` role, `P518` part,
statement-specific references, sibling source statements, and target-property
coexistence.  Missing inspection remains an abstention, never evidence of an
absent qualifier or reference.

Implemented CLI path:

```bash
python scripts/materialize_wikidata_migration_pack.py \
  --discover-company-direct --candidate-limit 25 \
  --source-property P5991 --target-property P14143 \
  --out-dir /tmp/nat-company-direct-page
```

It writes `manifest.json`, pinned current entity exports, a filtered current
slice, and the existing review-first migration pack. The discovery section of
the manifest is non-authoritative and records reconciliation outcomes even
when no row is eligible to enter classification.

## How this produces recommendations

This contract does not describe a system that invents new Wikidata ontology
policy. It describes a deterministic review packet for a bounded proposal.

This is the current bounded runtime slice of a broader formalism. In the latest
ITIR/SensibLaw framing, bounded migration packs are local projections of a
possible snapshot-derived global ontology index. The global formalism compiles
statements, constraints, disjointness surfaces, class-order surfaces, and
upstream references into typed carriers, computes residual/severity state, and
admits only candidate mutations satisfying:

```text
severity(after) <= severity(before)
```

If every applied edit in a finite residual lattice respects that filter, the
aggregate structural incoherence cannot increase and eventually reaches a fixed
point. This contract does not implement that whole global latent layer. It
implements one bounded review artifact that can later be one local projection
inside that larger coherence framework.

For the current climate lane, the bounded proposal is:

```text
review whether selected P5991 statements can be represented as P14143
```

The runtime recommendation is the row-level `action` field on each candidate,
such as `migrate`, `migrate_with_refs`, `split`, `review`, or `abstain`.
Those actions are review aids. They are not edit commands and they do not
override Wikidata community review.

The flow is:

1. Start with a bounded task, source property, target property, and source
   exports.
2. Build `slice.json`, grouping normalized statement bundles into windows.
3. Run `wikidata build-migration-pack` over the slice.
4. Produce `migration_pack.json`.
5. Classify each current-window source statement into buckets such as
   `safe_with_reference_transfer`, `split_required`, or `abstain`.
6. Export only review surfaces or checked-safe staging rows; keep uncertain
   rows held.

## File roles

| File or object | Role |
| --- | --- |
| `manifest.json` | Materialization inventory. It records the chosen QIDs, revision pairs, source export files, `slice.json`, `migration_pack.json`, and summary counts for a pack directory. |
| `slice.json` | Bounded source slice. It is the input to `build-migration-pack` and contains the normalized statement bundles grouped by window. |
| `migration_pack.json` | Contract output. It contains candidate rows, classifications, row-level actions, model/gate metadata, diffs, and summary counts. |
| `schemas/sl.wikidata_migration_pack.v1.schema.yaml` | Machine-readable contract for `migration_pack.json`. It is used to keep downstream code and review artifacts aligned on the same field names and allowed values. |
| `src/ontology/wikidata.py` | Manually written deterministic implementation that parses slices, builds candidates, computes diffs, classifies rows, builds gates, and exports review surfaces. |
| `cli/__main__.py` | Manually written CLI wiring that exposes `src/ontology/wikidata.py` functions as `wikidata ...` subcommands. |

## Generated versus authored

`schemas/sl.wikidata_migration_pack.v1.schema.yaml` is authored in the repo.
It is not generated from the Python program. When the payload shape changes,
the schema is updated deliberately and tests should validate that emitted packs
still conform.

`src/ontology/wikidata.py` is also authored in the repo. It is not generated
from the schema. The schema and program are kept aligned by tests, examples,
and review discipline, not by code generation.

## Contract shape
Schema version:

```text
sl.wikidata_migration_pack.v1
```

Top-level fields:
- `schema_version`
- `source_property`
- `target_property`
- `window_basis`
- `source_slice`
- `candidates`
- `summary`

## Window basis
The pack is built from:
- current window = last window in the bounded slice
- previous window = second-to-last window when present

Current `v0.1` interpretation:
- review is centered on current-window source-property bundles
- previous-window state is used only for drift/comparison surfaces

## Candidate contract
Each candidate row represents one current-window source-property statement
bundle.

### Atomic candidates and family context

A candidate is one statement GUID. Other current claims with the same
subject/property are retained as `statement_family_context`; they do not turn
an atomic candidate into a multi-value statement. The context may report scope
partitioning, duplicate/overlap signals, total/component reconciliation, and
whether all sibling source claims were supplied.

`split_required` is permitted only for an overloaded or otherwise ambiguous
source statement (or a documented climate-model condition on that statement),
not solely because siblings contain different values, years, or scopes. A
complete family of separately stated scoped components and total is assessed
as separate claims with `existing_partition_preserved`. A partial page must
hydrate complete sibling context from the pinned export or abstain from
family-level inference.

Required fields:
- `candidate_id`
- `entity_qid`
- `slot_id`
- `statement_index`
- `classification`
- `action`
- `confidence`
- `requires_review`
- `reasons`
- `split_axes`
- `claim_bundle_before`
- `claim_bundle_after`
- `qualifier_diff`
- `reference_diff`

### `claim_bundle_before`
The normalized current source-property bundle:
- `subject`
- `property`
- `value`
- `rank`
- `qualifiers`
- `references`
- `window_id`

### `claim_bundle_after`
The proposed target-property bundle candidate:
- same bundle shape as `claim_bundle_before`
- property rewritten to the target property only

Interpretation:
- this is a candidate migration projection, not an edit command
- no claim is made that every candidate should be promoted

## Runtime classification buckets in `v0.1`
Implemented buckets:
- `safe_equivalent`
- `safe_with_reference_transfer`
- `qualifier_drift`
- `reference_drift`
- `split_required`
- `abstain`

Reserved / deferred buckets:
- `needs_human_review`
- `non_equivalent`
- `safe_add_target_keep_source_temporarily`
- `ambiguous_semantics`

Reason for the split:
- `v0.1` is an executable review artifact first
- richer semantic/policy lanes still need more explicit repo-local rules

## Classification rules in `v0.1`
The initial runtime policy is intentionally conservative.

Promotion-adjacent safe buckets:
- `safe_equivalent`
  - current bundle is evidence-bearing
  - no slot-level qualifier drift across the comparison window
  - no slot-level reference drift across the comparison window
  - no multi-value ambiguity in the current slot
  - current bundle has no references to transfer
- `safe_with_reference_transfer`
  - same as above, but the current bundle carries references

Reviewer buckets:
- `qualifier_drift`
  - slot-level qualifier signatures or qualifier property sets changed across
    the comparison window
- `reference_drift`
  - slot-level reference signatures or reference property sets changed across
    the comparison window
- `split_required`
  - current slot has more than one distinct value
  - or one statement carries multiple temporal values / a start-end range
  - or sibling statements show a temporal split that cannot be migrated 1:1
- `abstain`
  - evidence gate not met in the current slot

## Runtime action field in `v0.1`
Each candidate also carries a narrow machine action:
- `migrate`
- `migrate_with_refs`
- `split`
- `review`
- `abstain`

Interpretation:
- `action` is the runtime recommendation attached to the candidate row
- it remains a review aid, not an edit command
- `split` means the current `P5991` statement looks decomposable rather than
  safely movable 1:1

## Bridge-ready additive surface
The next executable bridge slice may add review metadata without changing the
structured baseline.

Planned additive fields:
- top-level `bridge_cases`
- candidate `text_evidence_refs`
- candidate `bridge_case_ref`
- candidate `pressure`
- candidate `pressure_confidence`
- candidate `pressure_summary`

Interpretation:
- these fields are additive review metadata only
- they do not change the rule that structured migration review is the baseline
- they become meaningful only when promoted text observations are present

## General split rule
`split_required` is now driven by a property-agnostic test:
- does the source statement bundle encode multiple independent axes of
  variation that cannot be represented as one target statement without loss?

Current runtime shape:
- `split_axes` is emitted per candidate
- each axis records:
  - `property`
  - `cardinality`
  - `source` (`bundle` or `slot`)
  - `reason`

Current interpretation:
- `__value__` is used as the pseudo-axis when the slot contains multiple
  distinct source values
- qualifier properties become axes when they vary across the bundle or its
  sibling statement context

## Drift surfaces
`v0.1` surfaces two normalized drift summaries per candidate:

### `qualifier_diff`
- `status`
- `from_window`
- `to_window`
- `severity`
- `qualifier_property_set_t1`
- `qualifier_property_set_t2`
- `qualifier_signatures_t1`
- `qualifier_signatures_t2`

### `reference_diff`
- `status`
- `from_window`
- `to_window`
- `severity`
- `reference_property_set_t1`
- `reference_property_set_t2`
- `reference_signatures_t1`
- `reference_signatures_t2`

## Summary contract
Required fields:
- `candidate_count`
- `counts_by_bucket`
- `checked_safe_subset`
- `abstained`
- `ambiguous`
- `requires_review_count`

Interpretation:
- `checked_safe_subset` is the bounded subset eligible for later export work
- the pack remains a review artifact until a later lane adds explicit export
  and post-edit verification

Full-set interpretation:
- the current contract is already valid for full-set classification/filtering
- the current contract is not yet sufficient as a final migration-execution
  contract
- the main unresolved policy gap is now narrower:
  temporal/multi-value cases can graduate to `split_required`, but richer
  semantic buckets and post-edit verification are still missing

## OpenRefine bridge
The first operator-facing bridge should be review-first and flat-table shaped:

```text
SensibLaw MigrationPack -> OpenRefine CSV
```

The bridge does not emit Wikidata edits directly. It exports classified
candidate rows for OpenRefine faceting and review.

Recommended CSV columns:
- `candidate_id`
- `entity_qid`
- `slot_id`
- `statement_index`
- `from_property`
- `to_property`
- `value`
- `rank`
- `classification`
- `action`
- `confidence`
- `requires_review`
- `suggested_action`
- `split_axis_count`
- `split_axis_properties`
- `qualifier_drift`
- `reference_drift`
- `qualifier_diff_status`
- `reference_diff_status`
- `qualifier_diff_severity`
- `reference_diff_severity`
- `reference_count`
- `qualifier_count`
- `reason_codes`
- `notes`

Interpretation:
- OpenRefine is the human review / filtering surface
- SensibLaw remains the semantic classification layer
- edit execution stays out of scope for this bridge

Current operator claim:
- this bridge is strong enough for:
  - filtering a large/full candidate set
  - faceting obvious no-go cases
  - reviewing likely-safe subsets
- this bridge is not yet strong enough for:
  - fully trusted migration execution
  - final import payload generation for every row
  - precise machine action on all temporal/multi-value cases

Plain-language boundary:
- current checks are structured bundle checks, not source-text reading
- current output helps separate "probably safe" from "please review this"
- current output does not yet justify claiming that every row has a final
  machine action

## Checked-safe export
The first execution-adjacent export is deliberately narrower than the
OpenRefine review bridge:

```text
SensibLaw MigrationPack -> checked-safe CSV
```

Current contract:
- only rows already classified as:
  - `safe_equivalent`
  - `safe_with_reference_transfer`
- no drift/review rows
- no `split_required` rows
- no direct bot or QuickStatements emission

Current CSV fields:
- `candidate_id`
- `entity_qid`
- `slot_id`
- `statement_index`
- `classification`
- `action`
- `from_property`
- `to_property`
- `value`
- `rank`
- `qualifiers_json`
- `references_json`
- `target_claim_bundle_json`

Interpretation:
- this is a staging/export surface for already-safe rows only
- it is still not an edit command format
- downstream execution and post-edit verification remain separate gates

Immediate next policy goal:
- add a more precise action model for temporal/multi-value rows
- start by breaking some current `ambiguous_semantics` cases into
  `split_required` and related review actions
- keep execution/export claims gated until that action model exists
- if text-aware evidence is added later, route it through the bounded bridge
  contract in:
  `docs/planning/wikidata_phi_text_bridge_contract_20260328.md`
  rather than letting raw text interpretation bypass promotion or override the
  structured lane

## CLI contract
Build a pack from a bounded slice:

```bash
sensiblaw wikidata build-migration-pack \
  --input path/to/slice.json \
  --source-property P5991 \
  --target-property P14143 \
  --output path/to/migration_pack.json
```

Current CLI output summary fields:
- `output`
- `schema_version`
- `candidate_count`
- `checked_safe_subset_count`
- `requires_review_count`

## Live materializer helper
The bounded live helper now supports two QID population modes:

1. explicit inputs:
   - repeatable `--qid Q...`
   - or `--qid-file path/to/qids.txt`
2. bounded live discovery:
   - `--discover-qids`
   - `--candidate-limit N`
   - discovery is based on the source property and returns the exact QIDs used
     in the materialized manifest

Example with explicit QIDs:

```bash
.venv/bin/python SensibLaw/scripts/materialize_wikidata_migration_pack.py \
  --qid Q56404383 \
  --qid Q10651551 \
  --source-property P5991 \
  --target-property P14143 \
  --out-dir /tmp/p5991_p14143_pack
```

Example with bounded live discovery:

```bash
.venv/bin/python SensibLaw/scripts/materialize_wikidata_migration_pack.py \
  --discover-qids \
  --candidate-limit 10 \
  --source-property P5991 \
  --target-property P14143 \
  --out-dir /tmp/p5991_p14143_pack
```

One-step materialization plus OpenRefine CSV:

```bash
.venv/bin/python SensibLaw/scripts/materialize_wikidata_migration_pack.py \
  --discover-qids \
  --candidate-limit 10 \
  --source-property P5991 \
  --target-property P14143 \
  --out-dir /tmp/p5991_p14143_pack \
  --openrefine-csv /tmp/p5991_p14143_pack_openrefine.csv
```

Export a materialized migration pack to OpenRefine CSV:

```bash
sensiblaw wikidata export-migration-pack-openrefine \
  --input path/to/migration_pack.json \
  --output path/to/migration_pack_openrefine.csv
```

Export only the checked-safe subset:

```bash
sensiblaw wikidata export-migration-pack-checked-safe \
  --input path/to/migration_pack.json \
  --output path/to/migration_pack_checked_safe.csv
```

Verify the checked-safe subset against an after-state slice/export:

```bash
sensiblaw wikidata verify-migration-pack \
  --input path/to/migration_pack.json \
  --after path/to/after_state_slice.json \
  --output path/to/migration_verification.json
```

Current verification statuses:
- `verified`
- `duplicate_target`
- `target_present_but_drifted`
- `target_missing`

Current verification checks:
- only the checked-safe subset is examined
- does the exact target bundle exist in the after-state?
- if not exact, is there at least a same-value same-rank target row with drift?
- does the old source bundle still remain present?

## Split-plan followthrough
The next artifact after `split_required` detection is now a separate review-only
contract:
- note:
  `docs/planning/wikidata_split_plan_contract_20260328.md`
- schema:
  `schemas/sl.wikidata_split_plan.v0_1.schema.yaml`
- CLI:
  `sensiblaw wikidata build-split-plan`

Boundary:
- `MigrationPack` detects and explains split pressure
- `SplitPlan` proposes structurally decomposable `1 -> N` target bundles
- neither artifact is yet a direct split executor

## Non-goals
- no direct bot or QuickStatements emission
- no claim of semantic non-equivalence beyond the implemented buckets
- no automatic use of WikiProject consensus as promotion truth
- no direct edit execution in `v0.1`

## Immediate followthrough after `v0.1`
1. Add richer reference-transfer diagnostics.
2. Add policy-driven `needs_human_review` / `non_equivalent` lanes.
3. DONE: pin one real climate migration pack in-repo.
   - materializer:
     `SensibLaw/scripts/materialize_wikidata_migration_pack.py`
   - artifact root:
     `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`
   - stored together:
     - raw revision-locked entity exports
     - bounded slice JSON
     - derived migration pack JSON
     - manifest / artifact note
4. DONE: add a checked-safe export surface after the pinned pack exists.
5. DONE: add bounded post-edit verification over the checked-safe subset.
6. Define the first bounded bridge between:
   - structured migration-pack rows
   - promoted text observations
   - pressure outputs such as `reinforce`, `split_pressure`,
     `contradiction`, and `abstain`
