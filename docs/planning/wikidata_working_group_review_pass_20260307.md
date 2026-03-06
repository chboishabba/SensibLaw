# Wikidata Working Group Review Pass (2026-03-07)

## Session metadata
- Review date: 2026-03-07
- Reviewers: seeded for Niklas / Ege / Peter follow-up
- Slice identifier / dump window: `tests/fixtures/wikidata/live_p31_p279_slice_20260307.json`
- Report version: `wikidata_projection_v0_1`
- Source mode: `bounded local fixture`

## Findings summary
### 1. SCC neighborhoods
- SCC id: seeded live SCC 1
- size: 2
- member QIDs: `Q22652`, `Q22698`
- why this neighborhood matters: current live reciprocal `P279` pair; good for
  checking SCC surfacing without rank volatility
- action: `needs ontology-team discussion`

- SCC id: seeded live SCC 2
- size: 2
- member QIDs: `Q52040`, `Q188`
- why this neighborhood matters: second independent current live reciprocal
  `P279` pair; helps avoid overfitting the review process to a single SCC shape
- action: `diagnostic only`

### 2. Mixed-order nodes
- QID: `Q9779`
- observed `P31` / `P279` conflict pattern: same subject appears as both instance-of and subclass-of within the writing-system neighborhood
- affected neighborhood: `alphabet` -> `writing system`
- downstream deterministic risk: class-order traversals become brittle and can collapse instance/class assumptions
- action: `needs ontology-team discussion`

- QID: `Q8192`
- observed `P31` / `P279` conflict pattern: node appears in both subject and value roles across the bounded neighborhood
- affected neighborhood: `writing system`
- downstream deterministic risk: local hierarchy review becomes hard to interpret without explicit mixed-order diagnostics
- action: `diagnostic only`

- QID: `Q21169592`
- observed `P31` / `P279` conflict pattern: same subject appears as both
  instance-of and subclass-of `gene`
- affected neighborhood: `gene`
- downstream deterministic risk: demonstrates that mixed-order issues are not
  confined to writing-system curation and will recur in broader ontology slices
- action: `diagnostic only`

### 3. Metaclass-heavy regions
- target QID: `Q8192`
- evidence of metaclass-heavy use: receives `P31` incoming use while also participating as a structural type node in the same bounded neighborhood
- likely first-order alternative exists: unresolved in this pass
- action: `diagnostic only`

## Boundaries / non-goals check
- No auto-fix recommendation included: yes
- No authority leakage into internal ontology: yes
- No canonical text/token/lexeme mutation implied: yes
- No generative or regex-first authoritative mapping introduced: yes

## Open questions
- Slice gaps: current fixture now demonstrates multiple mixed-order examples,
  non-zero EII, and multiple confirmed live SCC examples; phase 2 has now
  produced confirmed live revision-pair qualifier-change cases, so the next gap
  is promoting one into repo-stable fixtures
- Threshold questions (`e0`, SCC priority, report ranking): keep `e0=1` for reviewer demos; revisit after first real multi-neighborhood slice
- Qualifier-drift follow-up: phase 2 now has a real imported qualifier-bearing
  baseline slice plus the bounded synthetic drift demo; live runs now also show
  confirmed medium-severity revision-pair drift on `P166` and `P54`; the
  primary current materialized case is `Q100104196|P166`
  (`2277985537 -> 2277985693`), and both that case and `Q100152461|P54`
  (`2456615151 -> 2456615274`) are now pinned in repo fixtures as the live
  phase-2 examples

## Next review actions
- keep `P31` / `P279` as the next bounded slice
- keep the structural pack stable while growing the importer-backed qualifier
  pack
- use `docs/wikidata_report_contract_v0_1.md` as the current reviewer-facing report contract
- record example status explicitly:
  - `alphabet` / `writing system`: `currently live`
  - `Na(+)-translocating NADH-quinone reductase subunit A CTL0002` / `gene`: `currently live`
  - `High German` / `German`: `currently live`
  - `urban green space` / `park`: `currently live`
  - `Q28792860` / `Maria Moors Cabot Prizes`: `currently live`, imported
    qualifier-bearing baseline (`P585`)
  - `Q1336181` / `Knight of the Order of the Dannebrog`: `currently live`,
    imported qualifier-bearing baseline (`P585`, `P7452`)
  - `Q100104196|P166`: `currently live`, primary materialized drift case from
    current broad run and now repo-pinned
    (`2277985537 -> 2277985693`, `medium`)
  - `Q100152461|P54`: `currently live`, second repo-pinned drift case from the
    current broad report (`2456615151 -> 2456615274`, `medium`)
  - `Q100243106|P54`: `currently live`, earlier observed drift case from live
    finder (`2462692998 -> 2462767606`, `medium`)
  - `referendum` / `plebiscite`: `historical thread example`
