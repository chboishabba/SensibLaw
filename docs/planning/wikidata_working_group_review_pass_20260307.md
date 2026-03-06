# Wikidata Working Group Review Pass (2026-03-07)

## Session metadata
- Review date: 2026-03-07
- Reviewers: seeded for Niklas / Ege / Peter follow-up
- Slice identifier / dump window: `tests/fixtures/wikidata/live_p31_p279_slice_20260307.json`
- Report version: `wikidata_projection_v0_1`
- Source mode: `bounded local fixture`

## Findings summary
### 1. SCC neighborhoods
- SCC id: none in the current fixture
- size: n/a
- member QIDs: n/a
- why this neighborhood matters: the current live demo case is mixed-order, not loop-driven
- action: `defer`

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
- Slice gaps: current fixture demonstrates mixed-order and EII, but not a live SCC case
- Slice gaps: current fixture now demonstrates mixed-order, non-zero EII, and a
  confirmed live SCC example; it still needs more neighborhoods before phase 2
- Threshold questions (`e0`, SCC priority, report ranking): keep `e0=1` for reviewer demos; revisit after first real multi-neighborhood slice
- Deferred qualifier-drift follow-up: keep deferred until more real `P31` / `P279` neighborhoods are imported

## Next review actions
- keep `P31` / `P279` as the next bounded slice
- import more real entity-export neighborhoods before qualifier drift
- use `docs/wikidata_report_contract_v0_1.md` as the current reviewer-facing report contract
- record example status explicitly:
  - `alphabet` / `writing system`: `currently live`
  - `urban green space` / `park`: `currently live`
  - `referendum` / `plebiscite`: `historical thread example`
