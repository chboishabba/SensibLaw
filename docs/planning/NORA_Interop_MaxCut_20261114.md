# NORA / production SLR / SensibLaw-reference / ITIR / DASHI integration: exact max-cut

## 15 November — original ITIR cohort ↔ actual SLR source DB receipt read-only consumer (new source)

**Operator prior reference:** SensibLaw `8a6605c27999f6e28041228354621f2d7d8e0bbb` **17/17 pytest**; later `f77b28f2` contains only prior documentation. **New tests and code below are SOURCE-WRITTEN / NEW HEAD UNVERIFIED.**

The existing `src/ontology/wikidata_nora_review_handoff.py` now includes `plan_nora_source_bound_persisted_review`. It first replays the NORA five-choice source-preserving handoff; requires a distinct explicit `wikibase_native_revision_id` rather than equating an article oldid, graph git SHA and Wikibase entity revision; binds actual ITIR physical cohort QID, original native statement GUID, target property, split references, original bin/graph rev/native SHA; recomputes SLR canonical candidate SHA and matches *both* committed PostgreSQL source-coordinate rows. It never pays source/semantic truth, Wikipedia first-link identity, native NORA export or edit authority. The supplied SLR JSON receipt is treated as **reported** DB evidence: this Python function does not itself run a DB query.

New adversarial tests are in `tests/test_wikidata_nora_review_handoff.py`; run `pytest tests/test_wikidata_nora_review_handoff.py`. Any provenance drift or caller-supplied authority flag fails closed.

Real NORA-author export, actual primary P854 reading/review, S29 legacy production consumer mapping and original publication authorization remain **OPEN**. See [ITIR physical cohort runbook](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/docs/planning/zelph_live_original_cohort_operator_runbook_20261115.md) and [SLR real DB bridge](https://github.com/chboishabba/slr/blob/agent/source-unit-wikimedia-handoff/docs/S29_REAL_SOURCE_REPLAY_20261115.md).

---


## Upstream native statement byte transport and SLR crosswalk — 15 November 2026

**Latest operator checks:** DASHI Agda 9/9, ITIR Python 120/120 + native mini-original `.bin` producer, SLR Rust 19/19, SensibLaw NORA Python 17/17 passed at the exact earlier source heads recorded in each PR. Since then ITIR #14 added an offline full Wikibase JSON raw SHA/QID/GUID/P14143/P854 verifier (19 isolated synthetic local tests) and a single original `.bin` source→native replay orchestrator (6 isolated tests). SLR #10 added typed raw-receipt ↔ graph/native candidate coordinate alignment (4 Rust tests source-written, not yet cargo checked).

**NORA role unchanged:** the historical SensibLaw read-only reference adapter cannot substitute for original Éder Porto NORA export, genuine five-choice/multi-consumer semantics, native primary source or persisted S29 production review. The new byte-level source artifacts should be treated as *candidate inputs*, not decisions or external Wikidata actions. Next production acceptance: actual original entity bytes, P854 source document review, SLR S29 restart and sparse dependency reopen, then authentic NORA source replay with current Nat full-GUID cursor.


## New A2 finite source boundary + B5 native SLR evidence gate — 15 November 2026

**Previously accepted baseline preserved:** DASHI seven Agda 2.9 modules PASS at `4c89edb`; ITIR 95/95 Python and four native packed Cap'n Proto roundtrips plus five controls PASS at `e64c04f`. Following these accepted commits, DASHI #1506 added a constructive (not yet kernel-checked) finite-query-word induction; ITIR #14 added explicit unnamed numeric frontier `--node` source routing and a finite left/right boundary closure reporter that refuses missing intermediate observations; SLR #10 added a source-written, not yet cargo-checked native Wikibase GUID/mainsnak/rank/qualifier/reference/P854 candidate join.

**NORA and Nat remain genuinely external/production:** retrieve an authentic source export of original Éder Porto NORA with original five choices, review provenance and per-consumer/standpoint semantics. Test real author-attributed read-only adapter → SLR native statement and durable S29 review/restart, retaining held/rejected choices. Current Nat full `(QID, statement GUID)` cursor and exhaustion receipt remains missing; the historical 57,989 P5991 statements and five-QID graph samples cannot substitute. No citation/source payment or external Wikidata edits follow from finite graph closure.


## New exact-head verified upstream gate / remaining true-NORA work — 15 November 2026

**ITIR #14 operator exact-head PASS at `e64c04f32f791502f6feccd3d918ece9a426c122`: 95/95 Python plus 4 real Cap'n Proto section roundtrips and 5 fail-closed native controls, clean tracked checkout.** This supersedes the earlier patched-worktree 90/90 state. **DASHI seven-module Agda 2.9 source gate passed** at source commit `4c89edbe`; both accepted results are *offline/formal source* checks, not the original live HF physical query proof.

**NORA still OPEN:** C5 requires the original Éder Porto NORA export/API fixture and source semantics (five choices, reviewer standpoint and consumer retained), with actual author attribution. B6 must join *the same source/revision/QID/GUID/consumer* to SLR's persistent S29 reviewed state and preserve held/rejected alternatives across a restart. C6 requires a current `(QID,statement GUID)` full Nat cursor and explicit exhaustion; historic 57,989 P5991 statements and five-entity fixtures do not pay this. No source payment or external edits from graph-only decisions.

**Production boundary:** SLR owns native statement/P854 provenance, S29 durability, reopen and external authorisation. SensibLaw #514 remains read-only reference/code handoff, not a second production execution owner. The [current golden A/B/C P0–P5 ledger](https://github.com/chboishabba/dashi_agda/blob/agent/nora-perspective-consumer-maxcut-20261114/Docs/ZelphTrieHyperfabricNatNoraMaximumCut20261114.md) supersedes dated older checkpoint paragraphs below.


## 2026-11-15 exact source verification / original HF physical cut

Reported operator local acceptance: ITIR previous 58/58 + 32/32 newly repaired Python synthetic physical controls = 90/90 in the patched worktree; the original unpatched ITIR head failed 9 tests. Source fixes are now committed, but the later ITIR native packed Cap'n Proto four-section roundtrip, source-offset hardening and same-run `--source-bin` re-verification remain **not yet locally replayed**. DASHI conditional Agda A1–A6 seven-target head `4c89edb` is verified in a clean local 2.9 run.

NORA must consume an attributed, real externally-authored original fixture before source-credit or reviewer authority changes. Neither source-bin equality nor graph one-hop exactness certifies native GUID, reference/P854 evidence or SLR S29. Preserve Éder Porto's original NORA authorship and separate read-only graph candidates from actual source adjudication.




## Agda 2.9 and ITIR 58-test checkpoint (after local verification report)

ITIR PR #14's targeted local suite now reports **58/58 tests passing** (earlier 41 superseded for those targets); SLR's candidate graph/native join reports **4/4** and this PR's NORA source/review reference adapter reports **17/17**. DASHI PR #1506 has now integrated the explicitly diagnosed A1 route-scoping fix, the coverage parse fix, query-indexed collision-repair implicit arguments and the original `0dc254eabe` core Set-sort changes. Agda was reported clean in the local patched worktree; only a **new exact-committed-head kernel run** will certify this PR head's golden mathematical import path.

**NORA/attribution status unchanged:** Éder Porto's authentic NORA native export/API fixture has not been received here, SLR S29 persistence and P854 source adjudication are open, and external Wikidata edit authority is not created by a pass, digest or graph candidate. Use [the same golden A1–A6/P0–P5 ledger](https://github.com/chboishabba/dashi_agda/blob/agent/nora-perspective-consumer-maxcut-20261114/Docs/ZelphTrieHyperfabricNatNoraMaximumCut20261114.md).



## 2026-11-14 verification checkpoint / updated upstream proof cut

Operator reported 17/17 scoped NORA handoff tests passing at PR #514 head `8a6605c`; this is a **reference adapter acceptance**, not an actual native export from Éder Porto or SLR S29 production persistence.

ITIR #14 now source-implements raw file-to-receipt replay, verified full **manifest-listed** name chunk cover and same-source-bin one-hop `left/right` adjacency comparison to independently decoded physical chunk bytes. They carry no native source/payment/editor authority, and the newer tests/C++ have not been rerun in this audit.

NORA acceptance remains: real author-attributed native export; subject/QID/revision/consumer/standpoint join; independent Wikidata GUID/mainsnak/quantity/qualifier/reference and P854 verification in SLR; S29 persistent review with dependency-scoped reopening; full current Nat population cursor/exhaustion; external edits only after separate authorisation. Preserve the original Éder Porto NORA credit and do not claim that candidate graph routing is a verified native reviewer decision.

[Golden A1–A6 and B/C/P0–P5 ledger](https://github.com/chboishabba/dashi_agda/blob/agent/nora-perspective-consumer-maxcut-20261114/Docs/ZelphTrieHyperfabricNatNoraMaximumCut20261114.md).



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

## Golden trie / hyperfabric foundational reconciliation

**[DASHI golden unified Zelph ↔ trie/ultrametric ↔ hyperfabric ↔ Nat/NORA max-cut](https://github.com/chboishabba/dashi_agda/blob/agent/nora-perspective-consumer-maxcut-20261114/Docs/ZelphTrieHyperfabricNatNoraMaximumCut20261114.md)** now classifies the work into six genuinely new mathematical propositions (A1–A6), six transport/semantic adapter obligations (B1–B6), and six empirical/production acceptance gates (C1–C6), organised as P0–P5 phases. It reuses the existing balanced-ternary `PrefixAgreement`, residual tree, indexed fabric, sheaf-style gluing, query-indexed sufficiency and nine-axis Nat admissibility. No new flat three-valued truth score or duplicate shard database.

An HF name chunk is **not automatically a ternary trie prefix ball**; a physical sorted-key/range map must be verified separately. The five-QID result is a reported exact physical name lookup, not native quantitative P14143 or P854 source payment. Actual NORA export remains separate.

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

**2026-11-14 empirical progress (operator report):** The pinned [ITIR five-QID HF route receipt](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/docs/planning/nat_zelph_hf_physical_route_execution_20261114.md) reports **21/21** targeted tests, direct Cap'n Proto name-shard reads, exact five-QID mappings and content-addressed route output. This advances **Z4/Z5 and the nodeOfName part of Z6** as *reported local execution*; raw input and receipt bytes are not yet independently reproducible from GitHub. The hosted manifest still does not advertise a `nodeRouteIndex`; the producer searched actual sorted name shards. **Z6 other section decodes, Z7 fetch-cost metrics, Z8 complete query-family evidence, Z9 SLR native review and Z10 real NORA export remain open**. Zelph's entity-linked graph cannot pay native quantitative P14143/P854 source-support obligations by itself.

## Zelph cross-pollination — reuse and evidence gates

**Current source-written follow-up:** [ITIR #14 strict `itir.shard.exact_wikidata_name_route` registration and tests](https://github.com/chboishabba/ITIR-suite/pull/14), [revision-pinned metadata-only HF probe](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/tools/probe_zelph_hf_nat_routes.py), [ITIR WIKI-US-05 and tool catalogue](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/docs/user_stories.md), [SLR production story crosswalk](https://github.com/chboishabba/slr/blob/agent/source-unit-wikimedia-handoff/docs/user_stories_wikidata_zelph_mcp_20261114.md). Agda golden, SLR production, SensibLaw historical reference. Exact-route code has source/tests but no new native test or live HF SHA/digest. The current blocker is network/DNS access for the live probe, not unknown canonical document paths.



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


## 2026-11-14 source implementation delta — NORA ⇄ physically audited name plane

On **existing PR #514**, `plan_nora_zelph_scoped_review` in `src/ontology/wikidata_nora_review_handoff.py` now checks ITIR's new exact byte-audited name-lookup and query-closure receipt schemas alongside a replayed attributed NORA handoff. It requires explicit source subject QID, equality across the lookup/closure graph revision, retention of consumer standpoint and five-choice judgement, physical candidate nodes for positive routes, and zero negative authority for missing-name results. Source revision and graph revision remain separate. Its digest-labelled output is a **review plan**, not a verified NORA native export, S29 persisted review, or external Wikidata edit.

Added negative tests to `tests/test_wikidata_nora_review_handoff.py` for mixed graph revisions, false negative promotion, missing-name abstention, and preservation of named source/standpoint. This does not duplicate the ITIR byte decoder or the SLR production store.

Acceptance command:
```bash
python -m pytest -q tests/test_wikidata_nora_review_handoff.py
```

Outstanding exact gates: native NORA fixture from Éder Porto (C5/N7), Agda kernel replay (C4/N9), original P14143/P854 source evidence and non-promoting S29 persistent review (B5/B6/C3), full revision-aware Nat `(QID, GUID)` population exhaustion (C6), and external edits only with operator permission and post-state/rollback receipts. None was established by the new tests.

[Golden exact lemma and P0–P5 ledger](https://github.com/chboishabba/dashi_agda/blob/agent/nora-perspective-consumer-maxcut-20261114/Docs/ZelphTrieHyperfabricNatNoraMaximumCut20261114.md).

## 21. CORRECTED: law-as-algebra is institutional schema crosswalking; NORA's value is not a distinct problem category (15 November 2026)

**This section supersedes the earlier Section 21 comparison.** The prior claim that NORA uniquely targets "institutional metadata-schema crosswalk authoring" whereas we mainly do evidence, constraints and governance is **incorrect**. We failed to account for SensibLaw's actual user stories, L0–L6 institutional ontology, legal-system/value-frame onboarding, cross-jurisdiction projections, and DASHI's law-as-algebra proof structure. These are already **institutional schema authoring, alignment, transformation and review problems**. Merely changing the institution from a museum to a court, regulator, local government, legal service, company or community normative system does not create a new mathematical problem class.

The valid remaining distinction is **scope/UX/current implementation maturity**, not product essence. Éder Porto owns independent NORA; no original NORA alpha code/export has been inspected or verified end-to-end here. The [author's Ontology Mapper technical plan](https://commons.wikimedia.org/wiki/File:Ontology_Mapper_-_Technical_Development_Plan_-_pt.pdf) documents institutional field-to-Wikidata mapping proposals, ranked candidates, five choices (*válida*, *inválida*, *ambígua*, *busca manual*, *lacuna de modelagem*), authoring/proposed properties, reused decisions, preview, exports and direct/federated Wikibase targets. These are intended capabilities, not proof of deployed alpha coverage. Our internal five-choice Agda model is **aligned with the documented author choices**, not a verified native NORA API schema.

### 21.1 What our own user stories actually require

| In-repository evidence | Real institutional authoring / mapping problem | Maturity claim we can support |
| --- | --- | --- |
| [SensibLaw ontology architecture](https://github.com/chboishabba/SensibLaw/blob/main/docs/ontology.md) | L0 source/utterance → L1 actors/events → L2 cases/claims → L3 legal systems/authority/provisions → L4 wrong types/elements/duties → L5 protected interests/harms → L6 value frames/perspectives/remedies; explicit **Programmatized Liability Stack (Crosswalk)** | Defined layered institutional ontology and crosswalk **contract**; not proof of complete authoring UI |
| [Ontology onboarding playbooks](https://github.com/chboishabba/SensibLaw/blob/main/docs/onboarding_playbooks.md) | Author a jurisdiction/authority hierarchy; seed legal sources, provisions, citations, wrong-type links, value-frame/cultural semantics; migrate and validate | Documented onboarding and checks; individual workflows must be tested separately |
| [SensibLaw user stories](https://github.com/chboishabba/SensibLaw/blob/main/docs/user_stories.md) | Regulatory applicability mapper; compliance/regtech analyst; institutional buyer/integrator; customer onboarding schema mapping; external counsel; regulator; Wikidata editor/ontology reviewer; personal-to-professional source handoff | **User stories** do not imply all product UI capabilities are deployed |
| [SensibLaw implementation coverage](https://github.com/chboishabba/SensibLaw/blob/main/docs/planning/user_story_implementation_coverage_20260326.md) | AU/Wikidata/GWB review geometry, central promotion gate, candidate/source bundles, split verification, source-follow and bounded personal handoffs | Explicitly distinguishes tested reference/CLI slices from wider unbuilt UX |
| [ITIR wiki stories](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md) | WIKI-US-01–04: revision-pinned qualified statement review, QuickStatements/OpenRefine tooling profiles, disjointness/migration candidates, cross-corpus reconstruction | Registered existing read-only MCP handlers; not arbitrary end-to-end schema wizard |
| [SLR production roadmap](https://github.com/chboishabba/slr/blob/main/docs/ROADMAP.md) | Source/revision/span→consumer residual→bounded acquisition→candidate→review/payment→world; **Sprint 4 M4.7 cross-jurisdiction projection**; M4.1–M4.6 workspaces, research UX, drilldown and exports | Sprint 1 reported certified at pinned head; Sprint 2 active; **Sprint 4 product is a roadmap, not a completed UI** |
| [DASHI statutory-rule algebra](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Cognition/PNF/SensibLawStatutoryRuleStructureAlgebraExact.agda), [legal world/revision](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Law/LegalWorldRevisionReconstructionExact.agda) | Typed provisions, jurisdiction-scoped definitions, authority roles, amendments/repeal, compilation into rules, temporally contextual world and dependence-aware reopen | Formal source declarations present; this audit did **not** re-run an exact-head Agda kernel acceptance |
| [ITIR architecture guide](https://github.com/chboishabba/ITIR-suite/blob/main/SL-arch-guide.md), [SLR roadmap](https://github.com/chboishabba/slr/blob/main/docs/ROADMAP.md) | One generic reconciliation algebra over typed semantic deltas/residuals; source identities are not DB surrogates; publication only at explicit authority boundary | Existing target execution architecture, not a basis for another NORA production store |

**A legal statute is institutional data with additional normative constraints**: institutionally scoped terms, roles and capacities, effective dates, hierarchies of binding authority, conditions, exceptions, defeaters, burdens, rights, duties and remedies. An ontology mapping from that source into the legal algebra is not an inferior form of GLAM catalogue field mapping; it is at least as demanding on semantics. Formal equivalence or label matching alone cannot grant legal applicability or truth.

### 21.2 Shared abstraction, not "our back end" versus "their authoring"

For a source schema S, target schema T, standpoint/observer o, legal or institutional world w, and consumer query q, a candidate schema morphism m is useful only if it preserves the query-relevant predicates and evidence identities. Use the *existing* DAG/typed hyperfabric and consumer sufficiency:

- **Draft**: a proposed source-field → target-property/class/relation mapping is an attributed candidate, not accepted truth.
- **Check**: test datatype, unit, cardinality/1-to-N, source anchors, hierarchy, authority, scope and time, and application-specific obligations.
- **Counterexample**: a collision with equal coarse projection but differing consumer answer is a concrete `ConsumerNonDescentWitness`. Recharting labels does not pay it.
- **Refine**: recover the first source-backed consumer-relevant residual, join sufficient observer axes, and recheck `FactorsThrough`; do not assume that every independently sufficient axis yields an adequate intersection.
- **Review**: different situated reviewers may legitimately produce nonidentical decisions; source, observer, consumer, validity window, access scope and actual evidence remain separate.
- **Admit**: the SLR review/payment gate, not either UI or external ontology, decides which bounded evidence can alter an admitted world. Export/public write requires an independent authority gate.

The same apparatus supports archive-to-Wikidata mapping, law-to-normative-algebra authoring, cross-jurisdiction legal applicability, GLAM institutional imports, and personal-to-professional record reinterpretation. **NORA is an optional external *peer front-end / source of mapping proposals*, not the human interpretation layer missing from our stack.** ITIR/SensibLaw already specify multiple human review and consumer workbenches.

### 21.3 Capability parity: distinguish problem solved from UX shipped

| Function | Ours | Native NORA | Differential evidence required |
| --- | --- | --- | --- |
| Institution-specific ontology/source schemas | Legal L0–L6, jurisdiction/source onboarding, external ontology refs and tests | Museum/archive/library source fields in author plan | Actual independent source examples on both sides |
| Candidate relation/mapping authoring | Ontology/split/constraint/reference routes plus planned richer workbench | Author plan has property ranking, five human choices, field authoring | Working UI/API traces, preserved exact source IDs |
| Modelling gaps & proposed terms | Diagnostic, abstention, native/migration candidates; typed residuals | Intended property-proposal drafting and manual search | Real missing-model case; draft expressivity and review cost |
| Collaborative decision reuse | Durable review/provenance and context-scoped reopening; no verified community-wide reuse wizard | Intended shared mapping memory | Real revision/observer-scoped reuse, negative-transfer controls |
| Preview/validated import export | ITIR batch tooling governance, source receipts; broader user-facing authoring/export not proven deployed | Intended example item and QuickStatements/OpenRefine exports | Exact item examples, datatype validity and no-write preflight |
| Formal semantic preservation | DASHI `FactorsThrough`, `ConsumerSufficient`, non-descent, legal-world semantics, hyperfabric | No native formal proof demonstrated | Source-specific invariant/counterexample and a kernel receipt |
| Durable production admission/replay | SLR owns; no new store | Native NORA data model unknown | If needed, one candidate-only adapter into existing SLR |

**Neither project gets credit merely for a roadmap.** Do not infer that ours has a polished universal crosswalk editor; do not infer NORA has deployed federation, batch export or superior accuracy from a design document. Also do not erase our institutional authoring use cases simply because the currently accepted product slice has more CLI/contract implementations than end-user UI.

### 21.4 Replace false "NORA vs our backend" experiment with shared-institution benchmark

Use **two complementary cohorts**:
1. **GLAM field crosswalk**: genuine immutable museum/archive/library metadata fields → appropriate Wikidata/Wikibase mapping with false-cognate, datatype, cardinality, 1-to-N, invalid and missing-property controls.
2. **Legal institutional crosswalk**: a revision-pinned statute/provision/definition, jurisdictional authority hierarchy and case/role relationship → existing SensibLaw legal ontology and qualified legal-rule structure; time-sensitive applicability, obligation/exception, cultural/standpoint and consumer non-descent controls.

The legal cohort tests *our* existing machine's representation and source-bound review and what an optional NORA generic mapping interface can express; **it is not fair to score NORA as failing its declared GLAM-focused product just because it does not implement full legal reasoning**. GLAM cohort tests both projects only for overlapping supported crosswalk operations. Report coverage and abstention instead of forcing unsupported tasks to produce scores.

Three *capability-scoped* arms: **Ours-as-built** (current CLI/MCP/reference/UI), **NORA-as-built** (real deployed author-exportable alpha), and **composition** (only if consented original NORA input/output supports a read-only bridge). Blind gold must be independent and preserve semantics, original field identity, source revision and context. Metrics: valid mappings per reviewer-hour, false equivalences, structural violations, recoverable provenance, modelling-gap accuracy, exact 1-to-N preservation, time and maintenance complexity, reviewer transfer between institutions, and subject-specific contextual sufficiency.

A GO threshold is a **proposal** (e.g., 20% operator-time benefit at noninferior correctness) rather than a finding. **NO-GO for integration** if overlap plus bridge cost gives no advantage; **LIMITED ADOPT** for an excellent specific UX/editor affordance. **NO EVIDENCE** if no original native author fixture or matched run; never manufacture performance figures. NORA does not need to "earn its keep" by solving legal ontology semantics; it must offer some empirically useful affordance in its actual product scope, and our collaboration must improve our own goals.

### 21.5 Corrected ownership and maximum-cut next deliverables

- Keep source authority and semantics at current owners: DASHI Agda #1506, ITIR #14, SensibLaw reference #514, SLR current source/evidence/S29 owners. No new ontology DB, solver, user-story suite, or separate NORA review-admission machine.
- Establish **law-as-algebra ↔ generic institution schema** mapping type with existing source-qualified object IDs, structured relation kind, typed constraints, time, legal source validity and consumer scope; reuse existing Agda law + observer theorem owners and SLR candidate/review state. This is a *new domain-specific bridge/fixture*, not a new core calculus.
- Produce a two-cohort reference suite and retain failed mappings as typed residuals. Distinguish **source-backed mathematical equivalence** from partial mappings, candidate similarities, and unknowns.
- Verify real original NORA alpha input/output schema, attributable author choice and export before proposing any native adapter; use the five choices from the original plan as **design context**, not guaranteed deployed data structures.
- Prioritize legal/GLAM crosswalk parity and source-preserving ergonomic comparison **after** existing SLR physical-source / same-source / persisted-replay gates; those independent production gates remain open whether NORA participates or not.

**Corrected conclusion:** The overlap is *larger* than our prior write-up admitted. Both projects address situated institutional schema mappings and review. Our law-as-algebra work is a substantial example of this. Possible NORA value is a particular authoring UI/community workflow or reuse mechanism, which must be demonstrated, not a supposedly unique capability class.
