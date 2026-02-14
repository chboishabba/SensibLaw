# DecisionObservation Projection Contract (v0.1)

This contract defines a **projection-only** view (`DecisionObservation`) that
allows shared descriptive aggregation plumbing across **domain-specific**
observation types without replacing them.

## Purpose
- Provide a stable, deterministic interface for descriptive aggregators to
  consume “decision episode” records across domains.
- Keep domain-specific records intact:
  - `CaseObservation` (judicial)
  - `ActionObservation` / `AlignmentObservation` (official/political)

## Non-Goals (Hard)
- No replacement of domain models with a generic storage table.
- No identity inference or cross-domain merging.
- No predictive modeling.

## DecisionObservation (Projection Shape)
Fields:
- `decision_id` (string; required)
- `actor_id` (string; required; explicit input)
- `actor_kind` (`judge|official`; required)
- `domain` (`judicial|political`; required)
- `jurisdiction_id` (string; required)
- `institution_id` (string; required)
- `date` (ISO date string; optional)
- `matter_type_id` (string; optional; e.g. `wrong_type_id` or `policy_area_id`)
- `predicate_keys[]` (array[string]; normalized, sorted, unique)
- `normative_reference_ids[]` (array[string]; normalized, sorted, unique)
- `output_label` (string; required; domain-specific label canonicalization lives upstream)
- `context_keys[]` (array[string]; normalized, sorted, unique)

## Projection Rules

### CaseObservation -> DecisionObservation
- `decision_id` = `case_id`
- `actor_id` = `judge_id` (required at projection time; empty actor_id is invalid)
- `actor_kind` = `judge`
- `domain` = `judicial`
- `jurisdiction_id` = `jurisdiction_id`
- `institution_id` = `court_id`
- `date` = `decision_date` (if present)
- `matter_type_id` = `wrong_type_id` (if present)
- `predicate_keys` = `predicate_keys`
- `output_label` = `outcome`
- `normative_reference_ids` = empty unless supplied from an upstream case-ingest lane
- `context_keys` = empty unless supplied from an upstream case-ingest lane

### ActionObservation -> DecisionObservation
- `decision_id` = `action_id`
- `actor_id` = `official_id` (required at projection time; empty actor_id is invalid)
- `actor_kind` = `official`
- `domain` = `political`
- `jurisdiction_id` = `jurisdiction_id`
- `institution_id` = `institution_id`
- `date` = `action_date` (if present)
- `matter_type_id` = `policy_area_id` (if present)
- `predicate_keys` = `predicate_keys` (feature keys for the slice/schema)
- `output_label` = `outcome_label`
- `normative_reference_ids` = supplied upstream (commitments invoked, statutes invoked) or empty
- `context_keys` = supplied upstream (constraint tags, posture tags) or empty

## Determinism
- Normalization is pure and deterministic.
- Lists are de-duplicated and sorted lexicographically after normalization.
- Output ordering is stable under input ordering changes.

