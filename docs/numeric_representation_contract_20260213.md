# Numeric Representation Contract (2026-02-13)

## Purpose
Define deterministic handling of numeric mentions for wiki/HCA AAO lanes so we can:
- coalesce by value safely,
- preserve precision and formatting provenance,
- avoid semantic drift from surface-string keys.

This contract separates numeric identity from numeric surface form.

## Layering
1. Span detection (parser-first): detect candidate numeric spans from spaCy entities/tokens.
2. Value parsing: derive normalized numeric value + unit/scale.
3. Numeric identity key: deterministic key used for coalescing/linking.
4. Surface phenotype: preserve source formatting metadata for display/provenance.

Truth must not collapse these layers into a single mutable string.

## Numeric Identity (truth)
Identity is value-based and unit-aware.

Required fields:
- `value_norm`: normalized decimal text (no grouping separators, no trailing zero noise).
- `unit`: optional (`percent`, `usd`, etc.).
- `key`: deterministic coalescing key.

Current key form in AAO/wiki views:
- `"<value_norm>|<unit>"` where unit may be empty.
- composite units are permitted when both scale and currency are explicit:
  - `"<value_norm>|<scale>_<currency>"` (example: `trillion_usd`)

Examples:
- `21`, `021`, `21.0` -> `21|`
- `68 percent`, `68%`, `68 per cent` -> `68|percent`
- `1.2 billion` -> `1.2|billion` (no silent expansion to an implied exact integer)
- `$5.6 trillion` -> `5.6|trillion_usd`
- `$500,000` -> `500000|usd`

## Surface Phenotype (provenance)
Formatting/surface form must be preserved separately from identity.

Examples of phenotype signals:
- compact suffix (`1.2billion` vs `1.2 billion`),
- symbol presence (`$`),
- textual form (`percent` vs `%`),
- source rendering artifacts.

These should never change identity keys; they are metadata for rendering, audit, and style analysis.

## Coalescing Rules
1. Coalesce numeric nodes by `key` only.
2. Keep first-seen readable label per key for display, with optional alternate surfaces list.
3. Never coalesce across different units.
4. Never infer missing units.
5. Never promote ambiguous parses to numeric identity.
6. Currency markers (`$`, `US$`, `A$`, `€`, `£`) are normalized into currency units;
   currency and non-currency values never coalesce.

## Precision Rules
- Do not silently inflate precision by converting scaled forms into expanded exact integers in truth labels.
- Preserve normalized decimal precision from source expression (`5.6 trillion` stays scale-aware, not fake exact integer form).

## Extraction Policy
Parser-first, regex-fallback-only:
- Preferred: spaCy `ents` (`CARDINAL`, `QUANTITY`, `PERCENT`, `MONEY`) and token `like_num` path.
- Fallback: regex mention scan only as safety rail.

Dropped mentions must fail closed (empty key), not surface-key fallback.

## UI/Graph Policy
Graph node IDs for numerics must use canonical key, not raw surface text.
- `num:<key>`
- Human-readable labels are derived separately from key/surface map.

This prevents raw-string fan-out (`21` vs `21,500`, `%` variants, compact suffix variants).

## Numeric Role Typing (v0.1, step-scoped)
Canonical numeric identity is necessary but not sufficient for reasoning. Numeric mentions
must also carry a role relative to their governing step/action.

Minimum role taxonomy for v0.1:
- `transaction_price`
- `personal_investment`
- `revenue`
- `cost`
- `rate`
- `count`
- `percentage_of`

Rules:
1. Attach numeric roles to the step that governs the numeric mention.
2. In multi-verb sentences, do not flatten all numerics under the first step.
3. Keep role typing deterministic and parser-first; use lightweight lexical fallbacks only when needed.
4. Role metadata must not alter numeric identity keys.

Example (target shape):
- `arrange/purchase ... for $89 million` -> `transaction_price`
- `invested $500,000` -> `personal_investment`

## Validation
Minimum regression set must assert:
- grouped number integrity (`21,500` does not leak `21` from same token group),
- `%`/`percent` equivalence,
- unit-only noise rejection (`billion` alone -> dropped),
- canonical key usage in graph linking.

## Non-goals (for now)
- locale inference beyond deterministic en-US compatible normalization,
- semantic role typing for all numeric relations (e.g., numerator/denominator semantics),
- automatic scale expansion into inferred exact integers.


## Ontology v0.1 (SL Numeric Claim Layer)

This section formalizes the target numeric ontology described in design reviews.
It extends the contract above while preserving deterministic parser-first extraction.

### Magnitude (identity anchor)
Represents pure unit-bearing magnitude, independent of source precision and formatting.

```yaml
Magnitude:
  id: "mag:{canonical_scientific}|{unit}"
  value: Decimal
  unit: string
  dimension: string
```

Identity rule:
- same iff `(value, unit)` are equal.

### QuantifiedClaim (epistemic statement instance)
Represents a source claim about a magnitude in context.

```yaml
QuantifiedClaim:
  id: string
  magnitude_id: string
  subject_id: string
  actor_id: string
  predicate: string
  time_scope: string
  modality: string
  significant_figures: int
  lower_bound: Decimal
  upper_bound: Decimal
  source_event_id: string
```

Notes:
- `1.2b` and `1.20b` should share `magnitude_id`.
- Precision belongs to `QuantifiedClaim`, not `Magnitude`.

### RangeClaim
Represents bounded claims like `1.2-1.7b`.

```yaml
RangeClaim:
  id: string
  lower_magnitude_id: string
  upper_magnitude_id: string
  subject_id: string
  actor_id: string
  predicate: string
  time_scope: string
  modality: string
  source_event_id: string
```

### RatioClaim / ProportionClaim
Represents structured quantitative relations (not flat independent numbers).

```yaml
RatioClaim:
  id: string
  numerator_magnitude_id: string
  denominator_magnitude_id: string
  subject_id: string
  actor_id: string
  predicate: string
  time_scope: string
  source_event_id: string
```

### NumericSurface (format phenotype)
Preserves expression form and rhetorical formatting without changing identity.

```yaml
NumericSurface:
  id: string
  claim_id: string
  original_text: string
  currency_symbol_present: bool
  compact_suffix_present: bool
  scale_word_present: bool
  spacing_variant: string
  thousands_separator_used: bool
  format_variant_code: string
```

### Comparison semantics
- Exact identity: same `magnitude_id`.
- Compatible precision: overlapping claim intervals with matching subject/scope.
- Conflict: non-overlapping intervals with matching subject/scope.

### Precision policy
- Do not silently inflate precision by expanding scaled forms into exact integers in truth labels.
- Keep scale-aware value identity and claim-local precision metadata separate.

## Implementation Status (2026-02-13)
Implemented now:
- parser-first numeric detection,
- deterministic key (`<value>|<unit>`),
- `%`/`percent` normalization,
- currency-aware key normalization from prefix/symbol forms (e.g. `$5.6trillion`),
- UI linking by canonical numeric key in AAO views.

Planned next:
- materialized `Magnitude` registry object in payloads,
- `QuantifiedClaim` objects with sig-fig and interval fields,
- `RangeClaim` and `RatioClaim` structured lanes,
- `NumericSurface` provenance map attached to claims.
