# NORA / production SLR / SensibLaw-reference / ITIR / DASHI integration: exact max-cut

Date: 2026-11-14. Scope: candidate-only NORA import and review replay.

**Population separation:** historical Wikimedia scope **57,989 P5991 statements**; the pinned **57-statement / five-entity sample** is only a regression fixture. No current full-population count or exhaustion receipt was checked in this tranche.

**Execution ownership:** SLR is the Rust production successor to SensibLaw. New NORA runtime transport and selective-review reopening must target SLR, not a parallel Python production pipeline. SensibLaw remains the source of Nat reference fixtures and its candidate-only adapter. [SLR production roadmap](https://github.com/chboishabba/slr/pull/18), [Nat/Wikidata native bundle](https://github.com/chboishabba/slr/pull/10), [native ontology comparison](https://github.com/chboishabba/slr/pull/51), [S29 governance](https://github.com/chboishabba/slr/pull/76).

## Reuse-first ownership

| Source owner | Reused contract | New code permitted |
|---|---|---|
| [SensibLaw Python](https://github.com/chboishabba/SensibLaw) | Typed canonical hashing and Nat reference fixtures | Reference adapter only, not production execution |
| [SensibLaw Nat PR #493](https://github.com/chboishabba/SensibLaw/pull/493) | Source support and 1-to-N calibration | Reuse tests and source contracts in SLR |
| [SLR PR #28](https://github.com/chboishabba/slr/pull/28) / [#57](https://github.com/chboishabba/slr/pull/57) | Production recurrent acquisition and provider-pinned materialisation | Reuse, no new scheduler/provider/database |
| [SLR PR #10](https://github.com/chboishabba/slr/pull/10) / [#76](https://github.com/chboishabba/slr/pull/76) | Existing Nat source-unit, statement bundle, S29/S30 review and governance | Wire NORA into these owners, not a new review store |
| DASHI ConsumerDescentMinimalObserverExact | Sectioned FactorsThrough and ConsumerSufficient | No substitute theorem |
| DASHI WikidataConsumerResidualRefinementExact | Noncollapse of failure origin | No new global truth score |
| DASHI SixfoldLogic / TetralemmaBridge | Qualified viewpoints and residuals | No C6/C3 same-object identity |
| DASHI ESD #1451/#1458 | Higher-order collision and evidence accounting | No fieldwise-sufficiency assumption |
| NORA (Éder Porto) | Original five-choice UI design | Await real export fixture |

## Exact max-cut gates

| Gate | Deliverable | Current status |
|---|---|---|
| N0 | Source/version/attribution-bound candidate handoff | Source implemented; offline tests with canonical test shim |
| N1 | Five choices without truth/action collapse | Source implemented; offline tests |
| N2 | Consumer-relative result and standpoint retained | Implemented as untrusted reported claims; proof validation external |
| N3 | Source snapshot, digest and replay | Implemented; repo-native typed hash acceptance pending |
| N4 | Nat 1-to-N split with source GUID and target bundles | Implemented retention guard; no public write |
| N5 | Source drift notification | Implemented pure recheck flag; SLR S29 selective reopen not wired |
| N6 | Manual-search acquisition request | Implemented plan-only output; SLR provider dispatch not wired |
| N7 | True NORA native export parser and round trip | OPEN: no pinned native sample or API fixture |
| N8 | Exact-head automated tests | Local 15/15 passed against test shim; real repo CI pending |
| N9 | Agda proof and cross-language witness | Source-written on separate Agda PR; Agda kernel acceptance OPEN |
| N10 | Actual Nat source proposition payment | OPEN: 42 ready / 15 blocked in prior executed receipt; zero paid |
| N11 | External checked-safe edit and rollback receipt | OPEN: requires operator rights, post-state and rollback |

## User-story reconciliation

Requirement owners: [ITIR user stories](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md), [SensibLaw editor story](https://github.com/chboishabba/SensibLaw/blob/main/docs/user_stories.md#wikidata-editor--ontology-reviewer), [SensibLaw story implementation coverage](https://github.com/chboishabba/SensibLaw/blob/main/docs/planning/user_story_implementation_coverage_20260326.md). SLR production contracts are expressed in the PRs and code below; this audit did not establish a separate SLR Nat user-story file.

| User-story owner | Existing accepted intent | Remaining NORA-specific obligation |
|---|---|---|
| [ITIR-US-17](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#itir-us-17-wiki-revision-review-assist) | Revision-locked wiki sections, cited links, bounded follows, explicit uncertainty | Replay an actual NORA source-revision/export into that workflow |
| [WIKI-US-01 / SL-US-38](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#wiki-us-01--sl-us-38-wikidata-statement-review-packet--batch-review-surface) | `itir.wikidata.review_packet.v1`, strict read-only statement/qualifier/reference review | Map the NORA decision and target bundles into the original packet ABI |
| [WIKI-US-02 / SL-US-39](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#wiki-us-02--sl-us-39-wikiproject-tooling--governance-profiles) | Versioned `itir.wikiproject.tooling_profile.v1` and governed external-tool capability | Add NORA as a verified candidate-only tool profile |
| [WIKI-US-03 / SL-US-40](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#wiki-us-03--sl-us-40-ontology-constraint--disjointness-violation-triaging) | `itir.wikidata.migration_candidate.v1`, disjointness and structural pressure | Show exact NORA relation and modelling-gap context in existing diagnostic output |
| [WIKI-US-04 / SL-US-41](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#wiki-us-04--sl-us-41-cross-corpus-wiki-to-sensiblaw-evidence-reconciliation) | `sl.wikidata_signal_review_bundle.v0_1`, wiki vs independent-source provenance | Preserve author/source/revision and never promote wiki prose into primary evidence |
| [SensibLaw Wikidata editor story](https://github.com/chboishabba/SensibLaw/blob/main/docs/user_stories.md#wikidata-editor--ontology-reviewer) | Review-first split planning, bounded follow, source revisions | Real NORA export test and operator experience |
| [SLR production acquisition/review](https://github.com/chboishabba/slr/pull/10) | PR #28 recurrent acquisition, #57 materialisation, #10 source handoff; PR #76 S29 candidate review | Actual provider queue, persisted selective reopening, returned verification receipts |

**Additional backlog-scale cut:** Existing Nat contract discovery demands a lossless composite `(QID, GUID)` cursor. The first two cumulative pages covered 400 revision-pinned statements; `population_exhausted=false`. To claim completeness, obtain full coverage and no-overlap/gap receipts for the current live population. Do not infer present backlog from the historical 57,989 figure.

The user stories specify intended behaviour; they do not establish that every workflow is compiled, deployed, reviewed or accepted.

## Native integration seam

Production route: NORA pinned export → [SLR source-unit / Nat statement bundle](https://github.com/chboishabba/slr/pull/10) → [SLR WIKI-1/relational diagnostics](https://github.com/chboishabba/slr/pull/51) → [existing S29 review path](https://github.com/chboishabba/slr/pull/76) → [recurrent source acquisition](https://github.com/chboishabba/slr/pull/28) → dependency-scoped reopening → review-first checked-safe export and separately authorised external execution. This is the **intended composition**, not a verified live end-to-end run. The Python NORA adapter in [SensibLaw #514](https://github.com/chboishabba/SensibLaw/pull/514) remains a test/reference producer.

ITIR implementation entry points: [review packet and migration candidate](https://github.com/chboishabba/ITIR-suite/blob/main/itir-mcp/src/itir_mcp/domain_tools.py) and [object review bundle](https://github.com/chboishabba/ITIR-suite/blob/main/itir-mcp/src/itir_mcp/wikidata_object_review.py).

**Current HF locator (14 November 2026):** [ITIR MCP canonical Zelph/Wikidata HF locator](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/docs/planning/zelph_hf_wikidata_mcp_locator_20261114.md) identifies upstream's documented `acrion/zelph` full and pruned-small manifest paths, exact QID/name lookup versus internal node routing, and the missing live immutable SHA/sidecar readback. The old July 2026 “no published metadata” finding is a historical checkpoint, not a current absence claim. ITIR MCP already exposes Wikidata review, migration, disjointness, and Zelph manifest/shard planning interfaces; these are not yet a verified NORA production round trip.

## Zelph cross-pollination — reuse and evidence gates

**Existing production order:** [SLR README](https://github.com/chboishabba/slr/blob/main/README.md): revisioned local P31/P279 → route-aware Zelph/HF graph snapshot → governed revision-pinned Wikidata fallback. This is a **source route**, not a truth predicate.

| Existing exact owner | What it actually contributes | NORA cut |
|---|---|---|
| [SensibLaw Nat PR #493](https://github.com/chboishabba/SensibLaw/pull/493) | Five QIDs resolved via Zelph; 57/57 native P14143 coverage coordinates paid; zero source-support admissions; hosted HF source acquisition and reasoned holds | Reuse revision-pinned native/graph evidence split; no automatic source support |
| [ITIR #14](https://github.com/chboishabba/ITIR-suite/pull/14) | Bounded `zelph-filtered-route/v1`, `itir.zelph_filtered_route_receipt.v0_1`; unresolved QID negative controls | No full graph sidecar or completeness assumption |
| [SensibLaw Zelph lane plan](https://github.com/chboishabba/SensibLaw/blob/main/src/ontology/wikidata_zelph_lane_plan.py) | Source-property broadening, migration target confirmation, split pressure; bounded SPARQL/route/partial-load proposals | Route `manual_search` and `modeling_gap` to evidence requests, not approvals |
| [SensibLaw disjointness lane proof](https://github.com/chboishabba/SensibLaw/blob/main/src/ontology/wikidata_zelph_lane_proof.py) | Bounded P2738/P11260 selector and transport receipt | Reuse WIKI-US-03 modelling diagnostics |
| [ITIR Zelph 0.9.6 lane audit](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/wikidata_lanes_zelph_096_status_20260703.md) | Distinguishes directly supported disjointness lane from adjacent Nat/climate discovery; hosted shard acceptance still distinct | Do not block other review work on full hosted graph publication |
| [DASHI Nat Zelph pipeline](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/SensibLawNatZelphPipelineExact.agda) | Routed P31/P279 graph evidence vs native statements; sound positive type module does **not** imply negative completeness, migration safety or edit rights | Preserve type, coverage and authority boundaries |
| [DASHI pruned artifact preservation](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/ZelphPrunedArtifactQueryPreservationExact.agda) | Query-family preservation is explicitly scoped to the pruned artifact | Never infer a global absence from an incomplete graph |

**New gates Z0–Z3 (all OPEN for NORA production):**

- **Z0:** Ground a NORA `manual_search` / `modeling_gap` request against a real pinned NORA fixture.
- **Z1:** Route through **SLR's existing** Zelph/local/live source-order and return exact snapshot, selector, query-family, execution and coverage receipts.
- **Z2:** Replay a positive and a missing-QID/partial-shard negative control without treating missing graph evidence as native Wikidata `novalue` or global contradiction.
- **Z3:** Transport candidate graph findings into the existing S29/ITIR read-only review packets; require independent P854 source-evidence adjudication and migration rights for any further step.

**Do not** create a second Zelph service, a second Nat graph index or a new review store. Zelph execution and SLR provider acquisition remain candidate-evidence surfaces.

**Shard audit and exact remaining physical gates:** [NORA Zelph Shard Transport Audit (Z4–Z10)](https://github.com/chboishabba/SensibLaw/blob/agent/nora-review-source-preserving-maxcut-20261114/docs/planning/NORA_Zelph_Shard_Transport_Audit_20261114.md). In particular, the prior v2 path has a measured ~51.95 MiB median node fetch envelope, ~700.53 MiB maximum, prior manifest fallbacks, stale-manifest cache risks and section-global name index corrections. Do not promote an unpinned transport plan or a passing sequential fallback.

## Test cases and expected results

1. NORA valid does not create semantic truth or edit authority.
2. NORA invalid can coexist with a positive result for another consumer.
3. Ambiguous, manual search, and modeling gap preserve distinct axes.
4. Split-required needs source GUIDs and at least two target bundles.
5. Source attribution, qualifiers and references survive import and replay.
6. A changed source revision causes review recheck, not an automatic edit.
7. An altered source, review, or consumer payload fails digest replay.
8. Consumer-factorisation proof labels remain untrusted until kernel validation.

## Formal owner

Agda source: DASHI/Ontology/NORAReviewPerspectiveProjectionExact.agda

Exact source-written declarations:
- searchIsAnAction
- gapIsAResidual
- ambiguousHidesDistinctSupport
- ambiguousIsNotSufficientForSupport
- ambiguousCannotFactorThroughSupport
- localValid / localInvalid
- qualificationDoesNotRewriteReview
- qualificationDoesNotRewriteSupport
- finiteDihedralCompatibilityReused
- sixfoldRotationReused

The module reuses the actual existing sixfold, tetralemma, C2/C3 and consumer non-descent owners. It does not identify physical C6 phases with sixfold epistemic statuses.

## Source and claim boundary

This is an INTERNAL mapping adapter. It is not a native NORA API integration.
A source transcript, reviewer choice or Boolean claim does not grant proof or edit authority.
Do not infer semantic truth from a checksum, QID, matched value or logical status.
No unqualified compatibility claim applies to Jain sevenfold logic, C2/C3 physics or zeta.

## Acceptance commands

In the SensibLaw checkout:

~~~bash
python -m pytest -q tests/test_wikidata_nora_review_handoff.py
python -m compileall -q src/ontology/wikidata_nora_review_handoff.py
~~~

In the DASHI checkout, run the pinned Agda checker for DASHI.Ontology.NORAReviewPerspectiveProjectionExact.

The isolated offline tests used a test shim for the typed canonical functions.
Run the actual repository tests before declaring a production result.
Then import one real NORA export with source revisions and independent attribution.

## Attribution

Original NORA design and review choices: Éder Porto.
Original Wikidata Lean checker: James Michael DuPont.
Classical Jain logic and cited mathematical methods retain their original scholars and source attribution.
The local adapters and negative controls are new integration work.
Do not relabel external contributions as local mathematical theorems.

## Reference URLs

- https://github.com/chboishabba/ITIR-suite/pull/14
- https://github.com/chboishabba/slr/blob/main/README.md
- https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/SensibLawNatZelphPipelineExact.agda

- https://github.com/chboishabba/SensibLaw/pull/493
- https://github.com/chboishabba/slr/pull/28
- https://github.com/chboishabba/slr/pull/57
- https://github.com/chboishabba/dashi_agda/pull/1029
- https://github.com/chboishabba/dashi_agda/pull/1143
- https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Core/ConsumerDescentMinimalObserverExact.agda
