# NORA and the Wikidata review tools: developer handoff

**To:** Éder Porto, NORA developer and project author  
**From:** DASHI / SLR / ITIR interoperability work (SensibLaw Nat reference lineage)  
**Date:** 14 November 2026  
**Status:** Technical proposal. No live NORA data exchange has passed a test.  
**Writing method:** ASD-STE100 Issue 9 style. This document has not passed a full controlled-dictionary audit.

## 1. Purpose

NORA helps a reviewer match a source field to a Wikidata property or class. The NORA development plan lists five review choices. A reviewer can use these choices to make a decision about a suggested match.

Our projects also review Wikidata statements. They keep the source data, the review decision, and the reason for that decision separate. We propose a small data exchange between these tools.

The data exchange must not change Wikidata. It must not treat a review choice as proof that a match is true.

## 2. What we already have

**SLR is the Rust production successor to SensibLaw.** [SLR PR #18](https://github.com/chboishabba/slr/pull/18) defines the production runtime. [SLR PR #10](https://github.com/chboishabba/slr/pull/10) already ports the Nat/Wikidata source-unit and statement-bundle review contracts. [SLR PR #28](https://github.com/chboishabba/slr/pull/28) adds recurrent acquisition. [SLR PR #51](https://github.com/chboishabba/slr/pull/51) adds source-native Wikidata diagnostics and comparison. [SLR PR #76](https://github.com/chboishabba/slr/pull/76) extends native review and governance. These PRs have different test and merge states.

**SensibLaw Python remains a Nat reference and calibration implementation.** [Nat PR #493](https://github.com/chboishabba/SensibLaw/pull/493) records the source acquisition and verification work. Its pinned climate pilot examines `P5991` to `P14143`. One source statement can require multiple target statements. Do not create a second production source collector or review store for NORA.

**ITIR** makes review packets. It keeps source identity, the review context, and access rules separate.

**DASHI** checks the limits of a mapping. It asks which questions a mapping can still answer. A mapping can work for one question and fail for another.

These tools do not replace NORA. They can check information that NORA does not need to show in its main review screen.

## 3. Meaning of the five choices

| NORA choice | Data exchange meaning | Do not assume |
|---|---|---|
| Valid | The reviewer supports this candidate. | The match is true for every use. |
| Invalid | The reviewer rejects this candidate in a stated context. | Every other user must reject it. |
| Ambiguous | The reviewer needs more information or sees conflicting evidence. | Missing evidence and conflicting evidence are the same. |
| Manual search | The reviewer requests another search. | The search has already run. |
| Modeling gap | The reviewer identifies a model problem. | Wikidata permits a new property or edit. |

Keep the original choice. Keep the reason and reviewer identity. Record the source revision that the reviewer used.

## 4. Requested exchange fields

Please provide a machine-readable export with these fields:

1. The source dataset ID, field ID, and source revision.
2. The candidate Wikidata property or class ID.
3. The proposed relation type and the method that produced the candidate.
4. The review choice, reviewer ID, review time, and review reason.
5. The source evidence references and any external source permissions.
6. The original author or source creator and the candidate producer, when known.
7. The target statement bundles for a one-to-many proposal, when applicable.
8. The version of the export format.

Do not insert unknown authors. Use an explicit unknown value when the source does not identify an author.

## 5. A concrete test: the Nat climate pilot

The original Wikimedia migration scope was **57,989 P5991 statements**. This is the historical project population, not a verified current live count. Our pinned five-entity test has 57 statement slots. One slot permits checked reference transfer. The other 56 slots need a split in the rebuilt test slice. The 57 slots are a test sample. They are not the migration workload.

For one split, we need the original statement GUID. We also need the proposed target statements. The proposal must keep the original qualifiers and references.

A reviewer can select **Valid** for a proposed match. That choice alone must not permit an automatic split or a public edit.

Our first exchange test will use a safe sample, not a public Wikidata edit.

## 6. Other important tests

**OEIS and QID:** Two values can match without naming the same mathematical object. Keep the type of match and the source.

**SI units:** Two fields can use the same unit but describe different quantities. Keep the quantity definition and its context.

**C2 / C3 / 369:** A finite symmetry can preserve one result but lose another result. Do not use matching state counts as proof of identity.

**Hyperfabric and intersectionality:** Each field can look correct while a group of fields loses an important relation. Keep the relation and its review context.

**Wikipedia languages:** A first-link navigation edge is not a subclass statement. Keep the language, article revision, and edge rule.

## 7. User stories and existing tools

The user stories already cover much of the proposed workflow.

- [**ITIR-US-17 — Wiki Revision Review Assist**](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#itir-us-17-wiki-revision-review-assist) calls for a fixed wiki revision, bounded cited-link follow, and a reviewer packet.
- [**WIKI-US-01 / SL-US-38 — Statement Review Packet**](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#wiki-us-01--sl-us-38-wikidata-statement-review-packet--batch-review-surface) calls for strict read-only statement review with qualifiers, rank, references, and item IDs.
- [**WIKI-US-02 / SL-US-39 — Tool Governance**](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#wiki-us-02--sl-us-39-wikiproject-tooling--governance-profiles) calls for an external-tool profile and clear edit permissions.
- [**WIKI-US-03 / SL-US-40 — Constraint Triage**](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#wiki-us-03--sl-us-40-ontology-constraint--disjointness-violation-triaging) calls for ontology constraints and candidate repair packets.
- [**WIKI-US-04 / SL-US-41 — Cross-Corpus Reconciliation**](https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md#wiki-us-04--sl-us-41-cross-corpus-wiki-to-sensiblaw-evidence-reconciliation) calls for source-attributed comparison with non-wiki evidence.
- The [**SensibLaw Wikidata editor / ontology reviewer** story](https://github.com/chboishabba/SensibLaw/blob/main/docs/user_stories.md#wikidata-editor--ontology-reviewer) calls for review and split help. The [implementation-coverage record](https://github.com/chboishabba/SensibLaw/blob/main/docs/planning/user_story_implementation_coverage_20260326.md) says some ordinary wiki-page source-follow paths remain partial.
- [**SLR PR #10**](https://github.com/chboishabba/slr/pull/10), [**SLR PR #28**](https://github.com/chboishabba/slr/pull/28), [**SLR PR #51**](https://github.com/chboishabba/slr/pull/51), and [**SLR PR #76**](https://github.com/chboishabba/slr/pull/76) carry the Nat review, acquisition, ontology diagnostics, and governed review work. SLR has no separate Nat user-story file established by this audit; the shared requirements live in ITIR and SensibLaw.

[ITIR's review API](https://github.com/chboishabba/ITIR-suite/blob/main/itir-mcp/src/itir_mcp/domain_tools.py) already defines `itir.wikidata.review_packet.v1` and `itir.wikidata.migration_candidate.v1`. [SensibLaw's Nat plan](https://github.com/chboishabba/SensibLaw/blob/main/docs/planning/wikidata_nat_end_product_and_tiered_automation_20260401.md) has split-plan and checked-safe export reference tools. [SLR's production recurrent acquisition](https://github.com/chboishabba/slr/pull/28) is the intended execution owner. Reuse its source and review contracts; the new NORA Python adapter must not become a parallel production runtime.

At scale, one live page is not proof of whole-population coverage. A complete Nat scan needs a source revision, a composite subject-QID and statement-GUID cursor, and proof that no page or statement was missed.

**Current HF locator (14 November 2026):** [ITIR MCP canonical Zelph/Wikidata HF locator](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/docs/planning/zelph_hf_wikidata_mcp_locator_20261114.md) identifies upstream's documented `acrion/zelph` full and pruned-small manifest paths, exact QID/name lookup versus internal node routing, and the missing live immutable SHA/sidecar readback. The old July 2026 “no published metadata” finding is a historical checkpoint, not a current absence claim. ITIR MCP already exposes Wikidata review, migration, disjointness, and Zelph manifest/shard planning interfaces; these are not yet a verified NORA production round trip.

**Latest reported Nat/Zelph execution:** The [ITIR physical-route report](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/docs/planning/nat_zelph_hf_physical_route_execution_20261114.md) records five Nat QIDs resolved directly from the HF full-graph **name shards** and a packaged route receipt, with 21 targeted tests reportedly passing. The canonical published manifest lacks an advertised route index, so the strict sidecar-based tool rightly blocked and the operator decoded the actual name chunks separately. This is useful evidence of live name routing; it does **not** mean the original NORA export, Zelph adjacency, quantitative Nat claims or SLR/Agda review is complete.

## 8. Zelph: reuse the existing graph evidence path

**Latest implementation crosswalk (14 November 2026):** [ITIR Wiki user stories including WIKI-US-05](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/docs/user_stories.md) now list the existing MCP tool library and state that Agda is golden, SLR is production, and Python SensibLaw is historical reference. [ITIR PR #14](https://github.com/chboishabba/ITIR-suite/pull/14) adds the strict `itir.shard.exact_wikidata_name_route` candidate-only MCP interface with negative tests and a [revision-pinned HF metadata probe](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/tools/probe_zelph_hf_nat_routes.py). [SLR PR #10's production user stories](https://github.com/chboishabba/slr/blob/agent/source-unit-wikimedia-handoff/docs/user_stories_wikidata_zelph_mcp_20261114.md) assign actual persisted Nat/S29 review to Rust. The live HF read was blocked by DNS; an actual QID→shard receipt and native NORA round trip remain open.



**Zelph is an existing part of our Nat and ontology work.** It can help find candidate relations and type links. It is not a source of automatic truth or edit permission.

[SLR's production acquisition order](https://github.com/chboishabba/slr/blob/main/README.md) is: local revisioned P31/P279 evidence, then a route-aware Zelph/HF snapshot, then a governed live Wikidata fallback. A missing result from a partial shard is not proof that a Wikidata statement does not exist.

The [SensibLaw Nat prerequisite work](https://github.com/chboishabba/SensibLaw/pull/493) already used Zelph for all five QIDs in the pinned test and paid 57 of 57 native P14143 coverage coordinates. It paid **zero** source-support propositions. This distinction matters: a graph relation, a Wikidata reference URL, and support from the referenced document are different types of evidence.

The [ITIR Nat filtered-route work](https://github.com/chboishabba/ITIR-suite/pull/14) defines `zelph-filtered-route/v1` and `itir.zelph_filtered_route_receipt.v0_1`. It does not need a full global graph sidecar. It keeps missing QIDs and incomplete coverage visible.

The [DASHI Nat/Zelph pipeline](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/SensibLawNatZelphPipelineExact.agda) keeps routed P31/P279 observations separate from native Wikidata statement authority. It also keeps partial-graph soundness separate from complete absence evidence.

[Existing SensibLaw Zelph lane planning](https://github.com/chboishabba/SensibLaw/blob/main/src/ontology/wikidata_zelph_lane_plan.py) proposes bounded discovery around the source climate property, target property, and split cases. The [bounded disjointness proof surface](https://github.com/chboishabba/SensibLaw/blob/main/src/ontology/wikidata_zelph_lane_proof.py) covers P2738/P11260. The [ITIR Zelph 0.9.6 lane audit](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/wikidata_lanes_zelph_096_status_20260703.md) says the climate demonstrator and Nat live-follow preflight do not have to wait for full hosted-shard acceptance.

For NORA, we propose this use: a reviewer selects **Manual search** or **Modeling gap**. SLR can prepare a bounded graph query through its existing Zelph route. The returned candidate must retain the query, graph revision, coverage receipt, source and reviewer decision. It must not become a verified Wikidata statement or migration decision without independent checks.

**What remains:** a true NORA input/output fixture; a native SLR request-and-result adapter that uses the existing Zelph transport; and a tested round trip that shows what happens when a QID is absent from a partial shard.

For the measured shard failure cases and next tests, see the [Zelph shard/transport audit](https://github.com/chboishabba/SensibLaw/blob/agent/nora-review-source-preserving-maxcut-20261114/docs/planning/NORA_Zelph_Shard_Transport_Audit_20261114.md). It records an earlier manifest fallback problem, a later cache-staleness problem and large remote fetch costs. Our NORA integration must first prove that direct shard reads work on the same pinned artifact. A route plan is not that proof.

## 9. What our adapter does now

The [SensibLaw reference branch](https://github.com/chboishabba/SensibLaw/pull/514) has a new candidate-only adapter, [`wikidata_nora_review_handoff.py`](https://github.com/chboishabba/SensibLaw/blob/agent/nora-review-source-preserving-maxcut-20261114/src/ontology/wikidata_nora_review_handoff.py). It receives a supplied candidate and review record. It does not parse an unverified NORA export.

The adapter retains the full supplied source. It retains the review and each consumer check. It uses the existing SensibLaw typed hash for replay.

The adapter refuses a missing source revision. It refuses a split with fewer than two target bundles. It also refuses changed review data during replay.

**Manual search** creates a request record. The adapter does not run a network request. The production work is an adapter into SLR's existing source/producer queue and selective reopening. That adapter has not been implemented or accepted in this PR.

## 10. What we ask you to do

1. Send one sample NORA export with the five review choices.
2. Include one example that maps one source field to two target statements, if NORA supports that case.
3. State how NORA records the source version and reviewer identity.
4. State whether a review can depend on a named use or context.
5. State whether NORA can keep an external residual or evidence reference.
6. Confirm how NORA handles later source changes and earlier review decisions.
7. Confirm which export actions require a person to approve them.
8. State whether NORA already uses Zelph, SPARQL, or another graph-query backend. If yes, identify its repository or query/output contract. We will reuse it rather than duplicate it.

If a field is not available, tell us. We can retain the missing detail in a separate review record.

## 11. Test and decision rules

**Pass:** We can import the supplied export and retain the complete source and review record. We can reproduce the original data from our saved handoff.

**Hold:** The export drops a source reference, a statement GUID, or a required split target. We keep the loss visible.

**Fail:** A review choice alone grants semantic truth, proof status, or public edit permission. The adapter must refuse that interpretation.

We will report each test separately. We will not claim that source collection proves a source proposition.

## 12. Attribution and source ownership

Éder Porto owns the original NORA design and implementation claims. DASHI owns its local formal mapping. **SLR owns the production runtime.** SensibLaw owns the original Python Nat implementation and the bounded reference adapter in [PR #514](https://github.com/chboishabba/SensibLaw/pull/514).

James Michael DuPont owns the original Wikidata Lean checker work. SLR keeps that source attribution when it imports the checker. Wikidata community policy controls public editing.

The mapping standards and the cited scientific sources retain their original authors. A software import does not transfer those claims to a new author.

## 13. Current limits

We have not checked the native NORA export format. We have not run a live NORA session. We have not performed a new SLR database replay for this adapter.

The adapter's consumer results are reported claims, not Agda kernel certificates. The Nat climate lane does not have verified unattended public edit authority.

## Source links

- NORA technical plan: https://commons.wikimedia.org/wiki/File:Ontology_Mapper_-_Technical_Development_Plan_-_en.pdf
- Nat migration status: https://github.com/chboishabba/SensibLaw/blob/main/docs/wikidata_working_group_status.md
- ITIR Wiki stories: https://github.com/chboishabba/ITIR-suite/blob/main/docs/user_stories.md
- SensibLaw story coverage: https://github.com/chboishabba/SensibLaw/blob/main/docs/planning/user_story_implementation_coverage_20260326.md
- Nat whole-population and cursor plan: https://github.com/chboishabba/SensibLaw/blob/main/docs/planning/wikidata_nat_end_product_and_tiered_automation_20260401.md
- Nat source acquisition PR: https://github.com/chboishabba/SensibLaw/pull/493
- SLR recurrent acquisition PR: https://github.com/chboishabba/slr/pull/28
- SLR classification and Zelph source order: https://github.com/chboishabba/slr/blob/main/README.md
- ITIR filtered Nat route: https://github.com/chboishabba/ITIR-suite/pull/14
- SensibLaw Nat Zelph and source coverage: https://github.com/chboishabba/SensibLaw/pull/493
- DASHI Nat-Zelph formal boundary: https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/SensibLawNatZelphPipelineExact.agda
- Zelph shard/transport audit: https://github.com/chboishabba/SensibLaw/blob/agent/nora-review-source-preserving-maxcut-20261114/docs/planning/NORA_Zelph_Shard_Transport_Audit_20261114.md
- SLR Nat/Wikidata statement-bundle handoff: https://github.com/chboishabba/slr/pull/10
- SLR production reader: https://github.com/chboishabba/slr/pull/18
- SLR native ontology and comparison: https://github.com/chboishabba/slr/pull/51
- SLR S29 ontology review: https://github.com/chboishabba/slr/pull/76
- ITIR review packet API: https://github.com/chboishabba/ITIR-suite/blob/main/itir-mcp/src/itir_mcp/domain_tools.py
- SensibLaw Nat editor story: https://github.com/chboishabba/SensibLaw/blob/main/docs/user_stories.md#wikidata-editor--ontology-reviewer
- Agda mapping PR: https://github.com/chboishabba/dashi_agda/pull/1143
- Agda sixfold logic: https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Algebra/SixfoldLogic.agda
- Agda consumer proof: https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Core/ConsumerDescentMinimalObserverExact.agda
- ASD-STE100 Issue 9: https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf
