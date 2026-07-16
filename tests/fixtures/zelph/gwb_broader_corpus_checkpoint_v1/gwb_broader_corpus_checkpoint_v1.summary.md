# GWB Broader Corpus Checkpoint Summary

This artifact is the first broader GWB extraction checkpoint beyond the
bounded checked handoff. It combines the checked handoff lane with fresh
deterministic extraction over the public-bios and corpus/book timelines.

## GWB Timeline QC Report

- **Source Event Count**: 887
- **Blocked Event Count**: 0
- **Active Event Count**: 887
- **Candidate Link Count**: 37638
- **Merged Event Count**: 6
- **Ordering Edge Count**: 1401
  - *Historical Time Order*: 222
  - *Document Order*: 789
  - *Ingest Order Only*: 915
  - *Historical Conflict Residual*: 141
- **Relations Dropped by Audit Block**: 0
- **Relations Preserved After Audit**: 17
- **Timeline Export (Chronology Only)**:
  - *Events*: 820
  - *Edges*: 222

## Merged coverage summary

- Source families: 3
- Distinct promoted relations: 17
- New relations beyond checked handoff: 2
- Distinct seed lanes: 13
- Seed lanes matched in multiple source families: 1

## Per-source-family summary

- checked_handoff: 19 promoted relations, 11 matched seed lanes, 9 ambiguous events, 7 unresolved surfaces.
- public_bios_timeline: 8 promoted relations, 3 matched seed lanes, 10 ambiguous events, 12 unresolved surfaces.
- corpus_book_timeline: 3 promoted relations, 1 matched seed lanes, 8 ambiguous events, 44 unresolved surfaces.

## New relations beyond checked handoff

- George W. Bush signed No Child Left Behind Act (from: public_bios_timeline).
- George W. Bush signed Northwestern Hawaiian Islands Marine National Monument (from: public_bios_timeline).

## Reading

- This is still a checkpoint, not full GWB/topic closure.
- It is the first machine-readable broader extraction pass over the
  public-bios and corpus/book timeline lanes rather than only an
  inventory of source families.

