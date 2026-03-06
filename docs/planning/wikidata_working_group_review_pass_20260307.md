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
  non-zero EII, and multiple confirmed live SCC examples; the next gap is real
  qualifier-bearing cases beyond the bounded phase-2 fixture
- Threshold questions (`e0`, SCC priority, report ranking): keep `e0=1` for reviewer demos; revisit after first real multi-neighborhood slice
- Qualifier-drift follow-up: phase 2 is now active in bounded form; next step is
  replacing the synthetic qualifier fixture with real imported qualifier-bearing
  slices

## Next review actions
- keep `P31` / `P279` as the next bounded slice
- keep the structural pack stable while adding real qualifier-bearing slices
- use `docs/wikidata_report_contract_v0_1.md` as the current reviewer-facing report contract
- record example status explicitly:
  - `alphabet` / `writing system`: `currently live`
  - `Na(+)-translocating NADH-quinone reductase subunit A CTL0002` / `gene`: `currently live`
  - `High German` / `German`: `currently live`
  - `urban green space` / `park`: `currently live`
  - `referendum` / `plebiscite`: `historical thread example`
