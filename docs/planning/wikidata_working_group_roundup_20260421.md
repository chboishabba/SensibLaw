# Wikidata Working Group Roundup: Climate Migration Routing

Date: 2026-04-21

## Purpose

Provide a concise working-group roundup for the Nat `P5991 -> P14143` climate
migration lane after the April 12 routing update.

## Short Version

The lane should now be read through two different axes:

- Nat cohorts: source/population buckets from the sandbox page.
- Routing families: action decisions after inspecting the row.

This matters because a row can be in a Nat source cohort but still route to
`full_auto`, `split_auto`, repair, review-only hold, or manual reconstruction
depending on its actual statement shape.

## Current Routing Families

### Family A: clean model-aligned rows

These are the rows suitable for `full_auto` after the normal checks:

- company item
- `CO2e` unit
- `GHG Protocol`
- single year
- clear scope or total

Route annual organization-level emissions to `P14143`.

### Family B: structured but needs split

These are the rows suitable for `split_auto`:

- multiple scopes on the same item
- totals and scopes mixed
- multiple years

The system should propose or verify split plans rather than flattening these
into one direct migration.

### Family C: model incomplete

These need repair plus migration:

- missing `P459`
- unclear method
- missing scope
- partial qualifiers

They are not failed rows; they are incomplete rows that need method/scope
clarity before promotion.

### Family D: valid subjects with weaker typing

These are review-only typed holds:

- not clearly company/org-level rows
- banks, organizations, or unusual `instance of`
- emissions not clearly organization-level
- emissions intensity
- avoided emissions, offsets, or removals
- product-level emissions or lifecycle carbon footprint
- other non-emissions metrics mixed into the surface

Do not force these into `P14143`.

### Family E: broken or legacy mixed rows

These need manual reconstruction:

- wrong units
- inconsistent qualifiers
- duplicate semantics
- mixed meanings in one statement

## Conservative Property Routing

- Annual organization-level emissions: route to `P14143`.
- Product/lifecycle carbon footprint: keep on `P5991`.
- Emissions intensity: typed hold, not `P14143`.
- Avoided emissions, offsets, removals: typed hold until a target property is
  confirmed.
- Non-emissions metrics: blocked.

## What This Means For The Current Nat Lane

The previous conclusion still stands: broad Cohort A sampling showed that many
rows are split/review work rather than direct one-to-one migrations. The new
routing table makes that sharper:

- Family A is the automation-readiness target.
- Family B is the split-plan target.
- Family C is the repair target.
- Family D is a review-only typed-hold target.
- Family E is manual reconstruction.

Recent repo progress has mostly been general compiler/admissibility work rather
than new Wikidata-specific routing code. That still helps this lane indirectly:

- stronger bounded extraction discipline
- stricter canonical-text and body-qualified substrate handling
- a clearer non-authoritative candidate layer through typed predicate carriers
- a more explicit residual/gating surface for exact, partial, mismatch, and
  contradiction states
- clearer shared candidate/report surfaces
- stronger separation between detection, review, and promotion/gating

So the Wikidata update should be framed as:

- no major change to the routing table itself
- some strengthening of the generalized review/control layer around it
- a stronger reason to treat all signals, including LLM outputs, as
  non-authoritative until they pass through a bounded review/gating surface

One concrete bounded example is now written down separately:

- `SensibLaw/docs/planning/wikidata_pnf_residual_review_example_20260429.md`

That note uses the real `Q10403939` (`Akademiska Hus`) climate case to show
why the newer canonical-text / PNF / residual framing strengthens the current
held split/review posture without claiming direct migration automation.

The useful next work is not another blind widening pass. It is measured routing
evidence: how many real rows land in A/B/C/D/E, and whether the Family A rows
stay stable across repeated verification.

## Ask For The Working Group

Please sanity-check the conservative routing table, especially:

- whether annual organization-level emissions is the right `P14143` boundary
- whether product/lifecycle footprint should remain on `P5991`
- whether emissions intensity, avoided emissions, offsets, and removals should
  stay held pending target-property confirmation
- whether missing `P459` should be treated as repairable rather than directly
  migrated

## Proposed Next Step

Run the next review pass as a routing evidence pass:

1. classify sampled rows into Family A/B/C/D/E
2. promote only stable Family A rows toward `full_auto`
3. send Family B through split verification
4. send Family C through repair/migrate review
5. keep Family D and E out of direct migration

This gives the group a clearer decision surface than a single yes/no migration
queue.
