# Wikidata Working Group Review Template (2026-03-07)

## Purpose
Use this template for bounded review sessions on the first Wikidata diagnostic
slice in SensibLaw/ITIR.

Current bounded slice:
- `P31`
- `P279`

Current goals:
- review mixed-order class/instance findings
- review `P279` SCCs
- review metaclass-heavy neighborhoods

## Session metadata
- Review date:
- Reviewers:
- Slice identifier / dump window:
- Report version:
- Source mode:
  - `live item snapshot`
  - `bounded local fixture`
  - `dump-derived slice`

## Findings summary
### 1. SCC neighborhoods
- SCC id:
- size:
- member QIDs:
- why this neighborhood matters:
- action:
  - `diagnostic only`
  - `needs ontology-team discussion`
  - `defer`

### 2. Mixed-order nodes
- QID:
- observed `P31` / `P279` conflict pattern:
- affected neighborhood:
- downstream deterministic risk:
- action:
  - `diagnostic only`
  - `needs ontology-team discussion`
  - `defer`

### 3. Metaclass-heavy regions
- target QID:
- evidence of metaclass-heavy use:
- likely first-order alternative exists:
- action:
  - `diagnostic only`
  - `needs ontology-team discussion`
  - `defer`

## Boundaries / non-goals check
- No auto-fix recommendation included:
- No authority leakage into internal ontology:
- No canonical text/token/lexeme mutation implied:
- No generative or regex-first authoritative mapping introduced:

## Open questions
- Slice gaps:
- Threshold questions (`e0`, SCC priority, report ranking):
- Qualifier-drift follow-up:

## Next review actions
- confirm next bounded slice or keep `P31` / `P279`
- nominate top neighborhoods for deeper review
- review the pinned live qualifier-drift cases and confirm whether
  signature-only drift should remain `medium`
- record whether each example is `currently live`, `historical thread example`,
  or `dump-reconfirmed`
