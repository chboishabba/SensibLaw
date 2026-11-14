# NORA / SensibLaw / SLR / DASHI integration: exact max-cut

Date: 2026-11-14. Scope: candidate-only NORA import and review replay.

**Population separation:** historical Wikimedia scope **57,989 P5991 statements**; the pinned **57-statement / five-entity sample** is only a regression fixture. No current full-population count or exhaustion receipt was checked in this tranche.

## Reuse-first ownership

| Source owner | Reused contract | New code permitted |
|---|---|---|
| SensibLaw canonical carrier | Typed canonical hashing | None; imported in adapter |
| SensibLaw Nat PR #493 | Source support and 1-to-N repair | Adapter-side snapshot and guard |
| SLR PR #28 / #57 | Recurrent acquisition and provider-pinned materialisation | No new scheduler, provider or database |
| SLR PR #10 / #76 | Source-unit review and S29/S30 boundaries | No SLR persistence claim |
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

| User-story owner | Existing accepted intent | Remaining NORA-specific obligation |
|---|---|---|
| ITIR-US-17 | Revision-locked wiki sections, cited links, bounded follows, explicit uncertainty | Replay an actual NORA source-revision/export into that workflow |
| WIKI-US-01 / SL-US-38 | `itir.wikidata.review_packet.v1`, strict read-only statement/qualifier/reference review | Map the NORA decision and target bundles into the original packet ABI |
| WIKI-US-02 / SL-US-39 | Versioned `itir.wikiproject.tooling_profile.v1` and governed external-tool capability | Add NORA as a verified candidate-only tool profile |
| WIKI-US-03 / SL-US-40 | `itir.wikidata.migration_candidate.v1`, disjointness and structural pressure | Show exact NORA relation and modelling-gap context in existing diagnostic output |
| WIKI-US-04 / SL-US-41 | `sl.wikidata_signal_review_bundle.v0_1`, wiki vs independent-source provenance | Preserve author/source/revision and never promote wiki prose into primary evidence |
| SensibLaw Wikidata editor story | Review-first split planning, bounded follow, source revisions | Real NORA export test and operator experience |
| SLR acquisition and review | PR #28 recurrent acquisition, #57 materialisation, #10 source handoff; PR #76 S29 candidate review | Actual provider queue, persisted selective reopening, returned verification receipts |

**Additional backlog-scale cut:** Existing Nat contract discovery demands a lossless composite `(QID, GUID)` cursor. The first two cumulative pages covered 400 revision-pinned statements; `population_exhausted=false`. To claim completeness, obtain full coverage and no-overlap/gap receipts for the current live population. Do not infer present backlog from the historical 57,989 figure.

The user stories specify intended behaviour; they do not establish that every workflow is compiled, deployed, reviewed or accepted.

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

- https://github.com/chboishabba/SensibLaw/pull/493
- https://github.com/chboishabba/slr/pull/28
- https://github.com/chboishabba/slr/pull/57
- https://github.com/chboishabba/dashi_agda/pull/1029
- https://github.com/chboishabba/dashi_agda/pull/1143
- https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Core/ConsumerDescentMinimalObserverExact.agda
