# Official Decision Behavior Contract (Descriptive-Only, v0.1)

This contract defines a **read-only descriptive aggregation** layer for elected
officials and other public officials. It is intentionally parallel to
`SensibLaw/docs/judicial_decision_behavior_contract.md` while staying **domain
distinct**.

## Purpose
- Provide deterministic, auditable summaries of **observed** official actions
  (votes/sponsorship/executive actions/etc) and (optionally) their alignment
  against explicit, time-bounded **commitments**.
- Support institutional review and corpus characterization without turning the
  core stack into a predictive scoring engine.

## Non-Goals (Hard)
- No prediction/forecasting of future behavior.
- No “probability this official will vote X”.
- No ranking/leaderboards/percentiles.
- No identity inference (no name matching, no fuzzy actor merge).
- No automatic commitment↔action linkage in this module (links are explicit
  inputs with provenance elsewhere).

## Determinism & Guardrails
These constraints align with:
- `SensibLaw/docs/panopticon_refusal.md`
- `SensibLaw/docs/ARCHITECTURE_LAYERS.md` (predictive behavior modeling is out of scope)

Requirements:
1. Output must be deterministic and order-independent.
2. Aggregation requires an explicit `SliceDeclaration` (no silent defaults).
3. All outputs must disclose:
   - `n_total` observations in the selected corpus
   - observed `time_min` / `time_max` bounds (if present)
4. Individual-level grouping is **disabled by default**. Grouping by
   `official_id` requires explicit `allow_individuals=true`.

## Data Model (Inputs Only; No Inference)

### ActionObservation
An “action episode” in the world (vote, sponsorship, executive order, etc).
This module does not ingest sources; it consumes normalized observations.

Fields (minimal):
- `action_id` (required)
- `jurisdiction_id` (required)
- `institution_id` (required)
- `institution_kind` (required; e.g. `legislature_house`, `legislature_senate`, `executive`)
- `action_date` (optional ISO date)
- `policy_area_id` (optional)
- `action_type` (optional; vote/sponsorship/amendment/exec_order/budget_line/...)
- `subject_key` (optional stable key for the subject: bill id, motion id, etc)

Feature schemas:
- Official action episodes may be tagged with predicate feature keys from a
  versioned feature schema. Example slice schema:
  - `SensibLaw/docs/official_behavior_feature_schema_us_exec_foreign_policy_iraq_v1.md`

### AlignmentObservation
A commitment↔action link with an explicit alignment label. This is the preferred
unit for “divergence” style summaries.

Fields (minimal):
- `link_id` (required; deterministic unique id for the link record)
- `action_id` (required)
- `jurisdiction_id` (required)
- `institution_id` (required)
- `institution_kind` (required)
- `action_date` (optional ISO date)
- `policy_area_id` (optional)
- `alignment` (required; `aligned|misaligned|ambiguous|not_applicable`)
- Optional individual-level fields (guarded):
  - `official_id`
  - `party_id`
- Optional context:
  - `constraint_keys[]` (e.g. `ctx.whip`, `ctx.confidence_vote`; descriptive tags only)

Notes:
- This contract intentionally keeps “commitment text” and “action text” out of
  this aggregation layer. Those belong in ingestion/provenance layers.
- Commitment↔action relevance scoring and linkage rules are outside scope here.

## Shared Projection (Optional)
If cross-domain descriptive plumbing is needed, project domain observations to
the projection-only `DecisionObservation` view (does not replace domain models):
- `SensibLaw/docs/decision_observation_projection_contract.md`

## SliceDeclaration (Required)
Each aggregation call must provide a `SliceDeclaration` object (JSON-friendly):
- `filters` (object; may be empty)
- `group_by` (array; must exactly match the function’s `group_by`)
- `time_bounds_declared` (object with optional `start`/`end`; may be null)

The goal is to prevent hidden conditioning defaults.

## Interpretation Guard (Mandatory)
All outputs must include:

> Observed rates/posteriors are empirical summaries of the selected corpus and
> slice definition; they do not imply causal tendency, personal disposition, or
> counterfactual behavior under different predicates or constraints.

## Output Contracts

### `aggregate_alignment_counts`
Returns deterministic counts of alignment labels by group.

### `aggregate_alignment_beta_binomial`
Returns a descriptive Beta-Binomial posterior over the **misalignment rate**
theta for each group (posterior over theta; not a predictive probability for
any particular future action).

Both functions must:
- be deterministic/order-independent
- require `SliceDeclaration`
- include corpus disclosure fields
- respect `allow_individuals` for `official_id` grouping
