# Wikimedia Prior Work and Originality Note

Last updated: 2026-03-26

## Purpose
Record, in one place, how the Wikimedia grant/demo lane should talk about prior
work, originality, method overlap, and forbidden wording.

This note is not a legal plagiarism ruling. It is a repo-governed submission
safety note to reduce the risk of:
- accidental plagiarism-style wording
- accidental overclaiming of novelty
- accidental collapse of "adjacent" into "reproduced"

## Scope
This note governs the Wikimedia grant/demo lane centered on:
- `docs/planning/wikimedia_grant_framing_20260326.md`
- `docs/planning/wikimedia_rapid_fund_draft_20260326.md`
- `docs/planning/wikimedia_bounded_demo_spec_20260326.md`
- `docs/planning/wikimedia_demo_attribution_matrix_20260326.md`

## Core rule
For final submission text:
- credit prior work explicitly when using its problem framing, comparison
  language, or method context
- describe repo overlap as `adjacent`, `partial parity`, `bounded`, or
  `fixture-backed` unless stronger repo evidence exists
- do not claim reproduction, parity, or first discovery unless repo docs
  explicitly support it

## Prior work reviewed

### 1. Rosario / IBM consistency-benchmark framing
Primary source:
- `2405.20163v1_rosario.pdf`

Paper title:
- `Reasoning about concepts with LLMs: Inconsistencies abound`

What it does:
- extracts concept hierarchies from a knowledge base/ontology
- creates test cases about hierarchy consistency and reasoning
- evaluates LLM inconsistency over those test cases
- uses KG-based prompting to reduce inconsistency

What this repo reuses as background:
- the general idea that bounded concept hierarchies can generate
  inconsistency-testing clusters
- the general benchmark/scorer framing for hierarchy/pathology-driven question
  generation

What this repo does not claim:
- exact method reproduction
- the same ontology flattening strategy
- the same primary truth surface
- a built-in live LLM-running pipeline equivalent to theirs

What appears repo-distinct:
- preserving structural pathology provenance instead of flattening `P31` and
  `P279` into one clean edge
- hotspot-family taxonomy over mixed-order, SCC, qualifier drift, and related
  pathologies
- deterministic fixture-backed benchmark pack selection
- bounded report/evaluator surfaces grounded in repo-local Wikidata fixtures

Safe wording:
- `partial parity with Rosario on benchmark/scorer shape`
- `adjacent to Rosario's benchmark framing`
- `the repo preserves structural pathology provenance rather than flattening it
  away`

Forbidden wording:
- `we reproduced Rosario`
- `our method is the same as Rosario's`
- `we independently originated the hotspot benchmark idea`

### 2. Ege Doğan / Peter Patel-Schneider disjointness work
Primary source:
- `2410.13707v2_ege.pdf`

Paper title:
- `Disjointness Violations in Wikidata`

What it does:
- studies disjointness violations in Wikidata
- extracts pairwise disjoint-class information from `P2738`
- counts subclass and instance violations
- identifies culprit classes/items
- uses SPARQL-based analysis and discusses better disjointness modeling

What this repo reuses as background:
- the importance of disjointness as a constraint surface
- the problem framing for Wikidata disjointness violations
- the idea of culprit-oriented disjointness diagnostics

What this repo does not claim:
- full method parity
- reproduction of the paper's full SPARQL method
- broader disjointness coverage beyond the bounded fixture-backed lane

What appears repo-distinct:
- bounded deterministic fixture-backed disjointness review lane
- explicit report contract and case-governance index
- integration with checked review surfaces and downstream Zelph/export context
- live-first candidate discovery paired with pinning reviewed slices into repo
  fixtures

Safe wording:
- `adjacent to Ege/Peter on the disjointness core`
- `method-adjacent, not yet parity`
- `the repo contribution is the bounded review/reporting implementation`

Forbidden wording:
- `we already have parity with Ege/Peter`
- `we reproduced the Ege/Peter method`
- `our current lane subsumes the paper's disjointness analysis`

### 3. Shixiong Zhao / Hideaki Takeda hierarchy-inconsistency work
Primary source:
- `2511.04926v2(1)_shixiong.pdf`

Paper title:
- `Diagnosing and Mitigating Semantic Inconsistencies in Wikidata's Classification Hierarchy`

What it does:
- studies semantic inconsistencies in Wikidata's classification hierarchy
- focuses on `P31` / `P279` misuse, over-generalized subclass links, and
  redundant connections
- proposes a validation/risk framework and a user-facing inspection system

What this repo reuses as background:
- the general framing that classification-hierarchy inconsistency is a live and
  important Wikidata problem
- the idea that user-facing inspection/diagnostic tools for hierarchy issues are
  valuable

What this repo does not claim:
- the same semantic risk model
- the same textual semantic embedding method
- large-scale hierarchy scoring parity

What appears repo-distinct:
- bounded provenance-aware review packs over pinned fixtures
- mixed-order/SCC/qualifier-drift/disjointness packaging in one checked review
  geometry
- stronger emphasis on explicit abstention, visible absences, and bounded
  review-support rather than global hierarchy scoring

Safe wording:
- `the proposal sits alongside recent hierarchy-inconsistency work by Zhao and
  Takeda`
- `the repo contributes a bounded provenance-aware review surface`

Forbidden wording:
- `we are doing the Zhao/Takeda method`
- `we independently originated the recent hierarchy-inconsistency framing`

## Attributed cases vs repo-owned surfaces
Use together with:
- `docs/planning/wikimedia_demo_attribution_matrix_20260326.md`

Practical rule:
- attributed cases such as `GNU` / `GNU Project` and the finance entity-kind
  collapse pack should not carry the novelty claim of the proposal
- repo-owned structural packs should carry the lead evidentiary story

## Safe originality claim
The safest current originality claim for the grant lane is:

- the repo contributes a bounded, provenance-aware, fixture-backed review and
  reporting surface over Wikidata structural pathologies
- it combines pinned structural packs, explicit review geometry, and
  deterministic outputs in a way that is useful for reviewer support
- it is informed by prior work on benchmark inconsistency, disjointness
  violations, and hierarchy inconsistency, but does not claim to reproduce any
  one of those methods in full

## Final submission wording rule
Before submission, check every strong novelty sentence against this note.

If a sentence implies any of:
- first discovery
- method reproduction
- parity
- unique invention of the problem framing

then either:
- add attribution and narrow the claim, or
- remove the sentence

## Remaining limit
This note is a careful originality/overclaiming pass, not a plagiarism-engine
comparison. It is good enough to govern submission wording, but not a claim that
all textual overlap risk has been mechanically measured.
