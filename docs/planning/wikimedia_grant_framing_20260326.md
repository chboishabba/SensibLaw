# Wikimedia Grant Framing for the Wikidata Lane

Last updated: 2026-03-26

## Purpose
Define the repo's current external-funding framing for the bounded Wikidata
 lane so grant-facing discussion does not drift into vague "fund SL/ITIR"
 language or get confused with the repo's internal review-surface status.

## Scope
- This note is about external Wikimedia funding/program framing only.
- It does not change the current implementation contract for the Wikidata lane.
- It does not imply that a grant application is active right now.

## Verified external funding state
An online check of official Wikimedia Meta pages on 2026-03-26 confirmed:
- Wikimedia funding is organized as recurring program lanes, not as one simple
  official list of "active Wikidata grants".
- The most relevant current entry points for this repo's Wikidata-adjacent work
  are:
  - `Rapid Fund`: short-term, low-cost Wikimedia projects; listed as
    `500 - 5,000 USD`, `1-12 months`, with `1 round per two months`.
  - `Wikimedia Research Fund`: research proposals; listed as
    `2,000 - 50,000 USD`, with `one round in a year`.
- Public proposal pages exist on Meta and can be mined for:
  - application structure
  - budget shape
  - reviewer feedback
  - funded vs rejected examples

Official pages checked:
- `https://meta.wikimedia.org/wiki/Grants:Programs`
- `https://meta.wikimedia.org/wiki/Grants:Programs/Wikimedia_Community_Fund`
- `https://meta.wikimedia.org/wiki/Grants:Programs/Wikimedia_Research_%26_Technology_Fund/Wikimedia_Research_Fund`
- proposal/discovery surfaces:
  - `https://meta.wikimedia.org/wiki/Category:Wikimedia_Community_Fund/Proposals`
  - `https://meta.wikimedia.org/wiki/Category:Rapid/Proposals/Funded`

## Strategic reading
Treat Wikimedia grantmaking here as a pattern-matching environment:
- do not wait for a perfect "grant for SL/ITIR"
- do not pitch the stack as an abstract system
- do fit the existing work into an already legible Wikimedia proposal shape

The practical move is:
1. inspect funded/rejected Wikimedia proposal pages
2. extract the common structure
3. map the current deterministic Wikidata lane onto that structure

## Recommended framing pattern
For the current repo state, the strongest Wikimedia-facing framing is:

`A provenance-aware Wikidata validation and ingestion tool`

More specifically:
- problem:
  Wikidata has bounded but real inconsistency, qualifier-drift, and
  unsupported-claim pressure that still needs reviewer time and better
  deterministic triage surfaces
- solution:
  a deterministic extraction, provenance, and review-support toolchain over
  Wikipedia/Wikidata slices
- impact:
  better Wikidata data-quality review, clearer provenance, lower editor review
  burden, and more trustworthy structured knowledge reuse

Related recent work to credit explicitly where relevant:
- classification-hierarchy inconsistency context:
  - Shixiong Zhao and Hideaki Takeda
- disjointness-violation method context:
  - Ege Doğan and Peter Patel-Schneider
- benchmark/consistency framing adjacent to the hotspot lane:
  - Rosario's IBM-affiliated consistency-benchmark framing

## Mapping from local stack to Wikimedia language
Use Wikimedia-facing language on the left of the proposal, and keep internal
 stack names secondary:

| Local concept | Wikimedia-facing framing |
| --- | --- |
| SL ingestion / deterministic extraction | Wikidata ingestion and validation pipeline |
| provenance / text-span receipts | verifiability and exact source support |
| Zelph reasoning / contradiction checks | constraint checking, contradiction review, issue triage |
| abstention instead of guessing | Wikimedia-aligned uncertainty handling and reviewer trust |
| bounded review packs | editor-facing review queues and diagnostics |

Do not lead with:
- "fund SL/ITIR"
- "abstract epistemic projection system"
- "general reasoning substrate"

Lead with:
- Wikidata validation
- provenance-aware review support
- deterministic ingestion/checking

## Two viable proposal shapes

### 1. Rapid Fund shape
Best if the ask is a small tooling/demonstrator proposal.

Suggested framing:
- build a bounded Wikidata validation and correction-support prototype
- publish the tool/repo/docs
- run it on a small, real Wikidata subset
- document reviewer-facing outcomes and limitations

Suggested deliverables:
- working prototype
- repo-public scripts/docs
- one bounded demonstration pack
- short operator/reviewer guide

### 2. Research Fund shape
Best if the ask is framed as a methodology/evaluation project.

Suggested framing:
- evaluate deterministic provenance-preserving extraction as an alternative to
  more heuristic knowledge-graph validation pipelines
- compare review quality, abstention behavior, and contradiction surfacing on
  bounded Wikidata cases

Suggested research claim:
- provenance-preserving deterministic extraction may improve reviewer trust and
  validation reliability by surfacing exact support and abstaining when support
  is weak

## Proposal skeleton to reuse
Any actual application should stay close to this structure:
- problem
- proposed solution
- impact on Wikimedia/Wikidata contributors
- concrete deliverables
- evaluation or success criteria
- budget

For this repo, the safe first title is:
- `Provenance-Aware Wikidata Validation and Ingestion Tool`

## Constraints
- External funding status must stay documented separately from internal repo
  readiness/status.
- Do not describe the current bounded lane as if it already solves general
  Wikidata ontology repair.
- Do not imply that Zelph or SL/ITIR are the thing being funded; they are the
  implementation substrate behind a Wikimedia-legible tool proposal.

## Next repo-facing step if funding becomes active
If this becomes operational rather than exploratory:
1. sample 2-3 funded and 2-3 rejected Wikimedia proposal pages
2. create a small maintained watchlist of relevant official funding pages
3. draft a concrete Rapid Fund first-pass application around the current
   deterministic Wikidata review/validation lane

## Current repo-local draft
The current concrete draft surface is:
- `docs/planning/wikimedia_rapid_fund_draft_20260326.md`
- `docs/planning/wikimedia_bounded_demo_spec_20260326.md`
- `docs/planning/wikimedia_demo_attribution_matrix_20260326.md`
- `docs/planning/wikimedia_prior_work_and_originality_note_20260326.md`

Those notes contain:
- a Rapid Fund-ready proposal draft
- one explicit bounded demo/evaluation collapse anchored in existing repo
  artifacts
- foreground repo-owned packs plus secondary attributed appendix examples
- preferred/fallback reviewer-route guidance
- one explicit prior-work/originality rule surface for final submission wording
- a ZKP (`O,R,C,S,L,P,G,F`) formalization to keep the proposal internally
  disciplined
- Wikimedia-style application fields
- explicit evaluation metrics and acceptance criteria
- a short risk/mitigation section for reviewer-facing submission hardening
