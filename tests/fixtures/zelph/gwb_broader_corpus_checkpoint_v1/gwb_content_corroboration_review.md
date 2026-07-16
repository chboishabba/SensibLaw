# GWB Timeline Content Corroboration Review Summary

This report evaluates the GWB checkpoint extraction as evidence, classifying corroboration, date confidence, merge risk, and contradictions.

## Merged Corroboration Summary

- **Total Reviewed Relations**: 17
- **Risky Merged Event Clusters**: 6
- **Conflict Packets**: 141

### Status Counts:
- **moderate**: 4
- **single_source**: 12
- **weak**: 1

## 1. High-confidence cross-source events

- No strong cross-source corroborated relations found.

## 2. Single-source events

- **George W. Bush nominated Harriet Miers** (source: checked_handoff)
- **George W. Bush nominated Samuel Alito** (source: checked_handoff)
- **George W. Bush signed Genetic Information Nondiscrimination Act** (source: checked_handoff)
- **George W. Bush signed Military Commissions Act** (source: checked_handoff)
- **George W. Bush signed Military Commissions Act of 2006** (source: checked_handoff)
- **George W. Bush signed Northwestern Hawaiian Islands Marine National Monument** (source: public_bios_timeline)
- **George W. Bush signed Syria Accountability Act** (source: checked_handoff)
- **George W. Bush vetoed SCHIP** (source: checked_handoff)
- **George W. Bush vetoed State Children's Health Insurance Program** (source: checked_handoff)
- **George W. Bush vetoed Stem Cell Research Enhancement Act** (source: checked_handoff)

## 3. Date/order uncertainty

- **George W. Bush signed No Child Left Behind Act** (confidence: `ingest_order_only`)

## 4. Historical conflict residuals

- **Edge ordering_edge:0011**: Conflict between `public_bios_timeline:ev:0006:atom:0000` (`2001`) and `public_bios_timeline:ev:0006:atom:0001` (`2000`).
- **Edge ordering_edge:0017**: Conflict between `public_bios_timeline:ev:0007:atom:0004` (`2001-september-11`) and `public_bios_timeline:ev:0008:atom:0000` (`1946-july-6`).
- **Edge ordering_edge:0019**: Conflict between `public_bios_timeline:ev:0008:atom:0001` (`2000`) and `public_bios_timeline:ev:0009:atom:0000` (`1995`).
- **Edge ordering_edge:0022**: Conflict between `public_bios_timeline:ev:0009:atom:0002` (`1995`) and `public_bios_timeline:ev:0010:atom:0000` (`1968-may`).
- **Edge ordering_edge:0029**: Conflict between `public_bios_timeline:ev:0011:atom:0004` (`2000`) and `public_bios_timeline:ev:0012:atom:0000` (`1975`).
- **Edge ordering_edge:0056**: Conflict between `public_bios_timeline:ev:0022:atom:0002` (`1978`) and `public_bios_timeline:ev:0022:atom:0003` (`1977`).
- **Edge ordering_edge:0062**: Conflict between `public_bios_timeline:ev:0024:atom:0000` (`2001`) and `public_bios_timeline:ev:0024:atom:0001` (`2000`).
- **Edge ordering_edge:0072**: Conflict between `public_bios_timeline:ev:0028:atom:0001` (`2003-november-27`) and `public_bios_timeline:ev:0029:atom:0000` (`2001-october`).
- **Edge ordering_edge:0073**: Conflict between `public_bios_timeline:ev:0029:atom:0000` (`2001-october`) and `public_bios_timeline:ev:0029:atom:0001` (`2001`).
- **Edge ordering_edge:0079**: Conflict between `public_bios_timeline:ev:0030:atom:0003` (`2005-january-20`) and `public_bios_timeline:ev:0030:atom:0004` (`2004`).

## 5. Audit-block affected relations

- No active relations affected by audit blocks.

## 6. Over-merged or under-merged event clusters

- **merged_event:0001** (None): risks: possibly_overmerged, date_span_too_wide, label_too_generic
- **merged_event:0002** (None): risks: possibly_overmerged, date_span_too_wide, label_too_generic
- **merged_event:0003** (None): risks: possibly_overmerged, date_span_too_wide, label_too_generic
- **merged_event:0004** (None): risks: possibly_overmerged, date_span_too_wide, label_too_generic
- **merged_event:0005** (None): risks: possibly_overmerged, date_span_too_wide, label_too_generic
- **merged_event:0006** (None): risks: possibly_overmerged, date_span_too_wide, label_too_generic

## 7. Coverage gaps

- **actor_uncertain**: 16 relations affected
- **date_inferred_only**: 16 relations affected
- **no_independent_corroboration**: 16 relations affected
- **no_primary_source**: 2 relations affected

## 8. Recommended next human review queue

- **George W. Bush nominated John Roberts** (degree: `moderate`, reasons: `['no_independent_corroboration', 'date_inferred_only', 'actor_uncertain']`)
- **George W. Bush ruled by United States Court of Appeals for the Sixth Circuit** (degree: `moderate`, reasons: `['no_independent_corroboration', 'date_inferred_only', 'actor_uncertain']`)
- **George W. Bush ruled by United States district court** (degree: `moderate`, reasons: `['no_independent_corroboration', 'date_inferred_only', 'actor_uncertain']`)
- **George W. Bush signed No Child Left Behind Act** (degree: `weak`, reasons: `['no_primary_source', 'no_independent_corroboration']`)
- **George W. Bush subject of review by Supreme Court of the United States** (degree: `moderate`, reasons: `['date_inferred_only', 'actor_uncertain']`)
