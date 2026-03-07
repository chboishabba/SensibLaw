# Bounded Wikidata Property/Constraint Pressure-Test Note

Date: 2026-03-07
Status: reviewed diagnostic note

## Purpose
Define deterministic pressure tests for property/constraint behavior that are
useful for ontology diagnostics, not ad hoc side discussions.

## Pressure-test domains
- financial-flow and time-series modeling
- subset-vs-total quantity representation
- practical loaded-property choices (including `supports` vs `P366`)
- user-facing label harmonization signals

## Test surfaces
- statement-level consistency across time windows
- qualifier stability by property family
- subset/total representation clarity in report projections
- property-choice ambiguity counts and abstentions

## Financial-flow/time-series checks
- detect mixed cumulative-vs-periodic usage for comparable quantities
- report qualifier/temporal-slot volatility that changes interpretation
- flag rows where timeseries alignment cannot be established deterministically

## Subset-vs-total checks
- classify rows as explicit total, explicit subset, or unresolved
- require explicit receipts when totals are inferred from subset-only evidence
- report unresolved subset/total ambiguity as a first-class diagnostic signal

## Property-choice checks (`supports` vs `P366`)
- surface when semantically adjacent properties produce materially different
  interpretation in the same neighborhood
- keep both candidates visible with deterministic scoring and abstention rules
- avoid "one true property" claims in this phase

## Label harmonization note (diagnostic only)
Signals like `type of XXX` vs `XXX subclass` are report-quality clues for
reviewer-facing inconsistency tracking; they are never treated as ontology
truth or schema authority.

## Deliverables
- deterministic report section for property/constraint pressure findings
- explicit unresolved bucket for loaded-property and subset/total ambiguity
- bounded fixture list for repeatable reviewer runs
