# Wikidata Nat Cohort B Review-First Bucket

Date: 2026-04-02

## Change Class

Standard change.

## Scope

This artifact is lane-local to **Nat Cohort B only**:

- all reconciled `instance of` classes outside the business-family tranche
  (`Q4830453`, `Q6881511`, `Q891723`)

This artifact does not classify or redefine Cohort C, D, or E behavior.

## Purpose

Define a bounded, review-first characterization for Cohort B so the lane can
separate high-variance reconciled classes from Cohort A while keeping qualifier
and reference variance explicit for reviewers.

## Cohort B Characterization

- bucket role: secondary reconciled-class tranche after Cohort A
- execution posture: review-first
- expected risk: higher semantic variance across subject classes and statement
  contexts
- migration posture: no blanket auto-migration claim from cohort membership
  alone

## Expected Qualifier Variance Surface

Baseline expected qualifier family (from the sandbox migration mapping):

- `P459` determination method or standard
- `P3831` object of statement has role
- `P585` point in time
- `P580` start time
- `P582` end time
- `P518` applies to part
- `P7452` reason for preferred rank

Review variance policy for Cohort B:

- if these qualifiers are missing where axis splits imply they matter, hold for
  review
- if additional qualifier properties appear, surface as variance rather than
  dropping silently
- mixed temporal qualifier resolution (`P585` vs `P580/P582`) remains explicit
  review pressure

## Expected Reference Variance Surface

Baseline expected reference family:

- `P854` reference URL
- `P1065` archive URL
- `P813` retrieved
- `P1476` title
- `P2960` archive date

Review variance policy for Cohort B:

- unexpected reference properties are reviewer-visible
- missing baseline reference fields in high-impact rows are review triggers
- reference preservation remains required where migration candidates are later
  approved

## Reviewer Questions (Cohort B)

1. Do class-specific semantics for this non-business reconciled class still
   support a carbon-footprint to GHG-emissions mapping?
2. Are split axes (`P518`, temporal qualifiers, method qualifiers) sufficient
   to prevent claim-boundary collapse?
3. Does the statement require additional class-local qualifiers before any
   migration-equivalence decision?
4. Do references ground the mapped claim at comparable specificity after split?
5. Is rank handling (`preferred` plus `P7452`) preserved or does the row remain
   review-only?

## Bounded Output Contract For This Bucket

- output class: Cohort B review packet or review-only row
- minimum visible fields:
  - class identity (`instance of` target)
  - qualifier/reference variance flags
  - split-axis pressure summary
  - unresolved reviewer questions
- explicit non-claim:
  - this bucket characterization is not full semantic decomposition and not an
    execution authorization by itself

