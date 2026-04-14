# GWB Broader Review

- Review items: `16`
- Source rows: `58`
- Covered source rows: `37`
- Missing-review source rows: `20`
- Related review clusters: `8`
- Candidate anchors: `177`
- Provisional review rows: `70`
- Provisional review bundles: `19`

## Derived Legal-Linkage Graph

- Nodes: `140`
- Edges: `298`
- Seed lanes: `16`
- Source rows: `58`
- Distinct source-row nodes: `58`
- Source kinds: `merged_promoted_relation: 18, seed_family_support: 28, source_family_summary: 3, source_row: 1, uk_legislation_receipt: 8`
- Source families: `EUR-Lex deterministic catalog: 1, checked_handoff: 2, checked_handoff,corpus_book_timeline: 1, checked_handoff,public_bios_timeline,corpus_book_timeline: 1, corpus_book_timeline: 2, national_archives: 1, public_bios_timeline: 2, uk_legislation: 2`
- Linkage kinds: `congressional_authority: 1, court_and_confirmation: 1, domestic_statute: 1, executive_proclamation: 1, institutional_anchor: 1, legal_reference: 1, litigation_and_subpoena: 1, statute_and_litigation: 1`
- Review statuses: `candidate_only: 1, matched: 1`
- Support kinds: `broad_cue: 1, direct: 1`
- Followed legal-cite classes: `eur_lex: 3, uk_legislation: 9`
- Brexit-related follows: `12`

### Graph inspection

- source_family: `checked_handoff`
- source_family: `checked_handoff`
- support_kind: `direct`
- review_status: `matched`
- linkage_kind: `domestic_statute`
- review_status: `candidate_only`

### Sample typed links

- `supports_source_row`: `Clear Skies legislative and Clean Air amendment lane` -> `gwb_us_law:clear_skies_2003 in checked_handoff`
- `mentions_source_family`: `gwb_us_law:clear_skies_2003 in checked_handoff` -> `checked_handoff`
- `mentions_source_family`: `gwb_us_law:clear_skies_2003 in checked_handoff` -> `checked_handoff`
- `mentions_support_kind`: `gwb_us_law:clear_skies_2003 in checked_handoff` -> `direct`
- `mentions_review_status`: `gwb_us_law:clear_skies_2003 in checked_handoff` -> `matched`
- `uses_linkage_kind`: `Clear Skies legislative and Clean Air amendment lane` -> `domestic_statute`

## Normalized Metrics

- Review-item statuses: accepted `7`, review_required `7`, held `0`
- Source statuses: accepted `37`, review_required `20`, held `0`
- Dominant primary workload: `linkage_pressure`
- Primary workload counts:
  - `structural_pressure` `0`
  - `governance_pressure` `0`
  - `linkage_pressure` `8`
  - `event_or_time_pressure` `3`
  - `evidence_pressure` `0`
  - `normalization_pressure` `0`
  - `queue_pressure` `0`
- Workload presence counts:
  - `structural_pressure` `0`
  - `governance_pressure` `0`
  - `linkage_pressure` `9`
  - `event_or_time_pressure` `3`
  - `evidence_pressure` `0`
  - `normalization_pressure` `0`
  - `queue_pressure` `0`
- Review-required source ratio: `0.344828`
- Candidate signal count: `70`
- Candidate signal density: `3.500000`
- Provisional queue rows: `70`
- Provisional row density: `3.500000`
- Provisional bundles: `19`
- Provisional bundle density: `0.950000`

## Top Provisional Review Bundles

- `#1` `family_summary:checked_handoff` anchors `2` top-score `16`
- `#2` `family_summary:corpus_book_timeline` anchors `2` top-score `16`
- `#3` `family_summary:public_bios_timeline` anchors `2` top-score `16`
- `#4` `gwb_us_law:congressional_subpoena_litigation:corpus_book_timeline` anchors `4` top-score `12`
- `#5` `gwb_us_law:defense_executive_operations:public_bios_timeline` anchors `4` top-score `12`
- `#6` `gwb_us_law:genetic_information_nondiscrimination_act:corpus_book_timeline` anchors `4` top-score `12`
- `#7` `gwb_us_law:military_commissions_2006:public_bios_timeline` anchors `4` top-score `12`
- `#8` `gwb_us_law:schip_veto:corpus_book_timeline` anchors `4` top-score `12`
- `#9` `gwb_us_law:schip_veto:public_bios_timeline` anchors `4` top-score `12`
- `#10` `gwb_us_law:supreme_court_appointments:corpus_book_timeline` anchors `4` top-score `12`
