# Zelph sharding and transport: source-grounded NORA/SLR acceptance audit

Date: 2026-11-14. Scope: reviewed source definitions and prior dated runtime receipts. This audit did **not** run a new remote HF probe, Zelph binary, Agda checker or SLR PG campaign. Older results do not prove current hosted state.

## Current upstream publication correction (2026-11-14)

The earlier July 4 ITIR observation that canonical hosted manifest/route/index objects were missing was **historical**. The current [upstream Zelph sharding documentation](https://zelph.org/sharding/) and [HF dataset card](https://huggingface.co/datasets/acrion/zelph) now document the **production-intended canonical published artifact paths**:

- full: `hf://datasets/acrion/zelph/wikidata-20260309-all/wikidata-20260309-all.hf-v2.json`
- pruned-small: `hf://datasets/acrion/zelph/wikidata-20260309-all-pruned-small/wikidata-20260309-all-pruned-small.hf-v2.json`
- manifest-side shard layout: `<artifact>/shards/{left,right,nameOfNode,nodeOfName}/...` and `<artifact>/artifact.index.json`

The upstream documentation explicitly includes `.load-partial` commands against these manifests. **That is stronger evidence of publication than the earlier July audit**, though a fresh live manifest/sidecar payload and current immutable revision/checksum remain unverified by this connector.

**Source and MCP locator:** [ITIR PR #14 — exact HF/Wikidata MCP locator](https://github.com/chboishabba/ITIR-suite/blob/agent/nat-filtered-route-producer/docs/planning/zelph_hf_wikidata_mcp_locator_20261114.md).

ITIR MCP **already registers** `itir.wikidata.review_packet`, `object_review_bundle`, `migration_candidate`, `disjointness_report`, and the `itir.zelph.hf_manifest_contract`, shard routing/planning/probing and partial-closure tools. Exact QID-to-shard tracing must proceed from **external name** → `route-name=Q... route-lang=wikidata` → internal node ID → `route-node=<internal-id>` on the *same* artifact. Upstream explicitly notes that name-section `chunkIndex` is section-global and that `route-node` IDs are artifact-local.

One further acceptance hazard: [ITIR shard_transport.route_selector](https://github.com/chboishabba/ITIR-suite/blob/main/itir-mcp/src/itir_mcp/shard_transport.py) permits coarse family-only fallback when the exact sidecar has no match. For production Nat/NORA, such a result must be called **coarse selection**, not exact QID routing; it needs an exact matched selector witness to claim precise routing.

## Verdict

The programme already models Zelph transportation, coverage, partial/sharded graph queries, and SLR physical-object acquisition. The practical remaining cut is **not creating a query plan**. It is proving a bounded, revision-pinned **manifest → route → physical shard → decode → query-family coverage → review receipt** chain on one actual publication. Successful fallback and successful bytes fetched cannot substitute for direct shard acceptance or semantic completeness.

## Recorded faults and evidence

| Failure or measured cost | Verified source | Evidence and resolution boundary |
|---|---|---|
| Cap'n Proto manifest decode/fallback | [ITIR partial-load harness](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_partial_load_harness_20260326.md) | Older manifest chunk reads could fail decode and recover by sequential `.bin` fallback. The recorded v2 left-chunk fallback was **not** direct shard success. Harness differentiates direct/fallback/hard failure. |
| Section-global `chunkIndex` mismatch | [ITIR July readiness](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_develop_sparql_partial_load_readiness_20260702.md) / [amended storage contract](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_hf_storage_contract_20260326.md) | `nameOfNode` and `nodeOfName` indices must be section-global on post-fix artifacts, not restarted per language. Recheck emitted index, manifest and selected chunks against the *same* blessed binary. |
| Missing canonical hosted metadata (historical July checkpoint) | [ITIR July readiness](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_develop_sparql_partial_load_readiness_20260702.md) | July 4 recorded public HF shard directories and bounded direct selected reads, but did **not** find canonical manifest, route sidecar and index as hosted acceptance objects. Current upstream documentation now specifies canonical published paths; the current immutable revision and bytes **remain unverified**. |
| In-place manifest cache staleness | [ITIR HF storage contract July 14 note](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_hf_storage_contract_20260326.md) | Open-ended `length=0` cached manifest survived an in-place patch, pointing a consumer at superseded local `source.binPath`. Revalidate manifest by revision/ETag; immutable payload caches must be tied to the manifest/object version. |
| Excessive v2 fetch amplification | [ITIR measured route budget](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_hf_storage_contract_20260326.md) | Recorded 2026 shard-route estimates: node median **51.95 MiB**, p95 **60.63 MiB**, max **700.53 MiB**; exact-name median **21.70 MiB**. These are *prior estimated fetch envelopes*, not live latency measurements or verified v3 reductions. |
| Route index and query shape | [Proposed v3 contract](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_hf_v3_shard_contract_20260326.md) | The v2 layout is based on original packed chunk boundaries. Proposed v3 bucket adjacency by source/target, name by language and hash, compact route sidecar, one-sided lookup. Targets: left/right median <10 MiB, symmetric median <20 MiB, route-name median <10 MiB; these are **not accepted performance results**. |
| Logical requests ≠ physical concurrency | [DASHI SLR physical-object policy](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/SLRGWBPhysicalObjectAcquisitionPolicyExact.agda) | Resolve QIDs to physical shard requests, deduplicate/coalesce first, then enforce concurrency at object level. The formal gate marks several providers/scheduling/telemetry components `implementedAwaitingRuntime`, not runtime-proven. |
| Partial fetch ≠ absence | [DASHI bounded coverage](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/ZelphBoundedGraphCoverageExact.agda), [pruned query preservation](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/ZelphPrunedArtifactQueryPreservationExact.agda) | Typed source boundaries distinguish transport complete/partial/failed from per-query complete/incomplete/uninspected/invalid. Source-to-pruned *completeness* needs a query-family-specific, source/revision-bound certificate; positive monotone soundness alone is insufficient. These are static formal carrier/negative-control statements, not an end-to-end external runtime certificate. |
| Exact QID despite graph-route miss | [DASHI dual identity](https://github.com/chboishabba/dashi_agda/blob/master/DASHI/Interop/SensibLawNatDualIdentityConfirmationExact.agda) | An independent revision-pinned Wikidata export may confirm QID identity and native family even if Zelph's `nodeOfName` partition misses it. The Zelph route coordinate stays unresolved; source support and edit authority stay open. |
| NORA cannot infer runtime acceptance from graph plan | [ITIR shard_transport.py](https://github.com/chboishabba/ITIR-suite/blob/main/itir-mcp/src/itir_mcp/shard_transport.py), [ITIR bounded-graph tests](https://github.com/chboishabba/ITIR-suite/blob/main/itir-mcp/tests/test_shard_transport.py) | `build_bounded_graph_slice_view` is a selector/fetch **plan**; even selection of every shard may report incomplete semantic coverage. Native SLR review needs the later fetched/decoded/validated result receipt. |
| Current Nat filtered route | [ITIR PR #14](https://github.com/chboishabba/ITIR-suite/pull/14), [Nat #493](https://github.com/chboishabba/SensibLaw/pull/493) | Bounded five-QID route with coverage/identity receipts exists. Five-QID path and 57 native property checks do not establish all 57,989 historical statements, source support or arbitrary NORA graph queries. |

## Reusable pre-existing infrastructure

- [SLR README production order](https://github.com/chboishabba/slr/blob/main/README.md): local/revisioned type slice → Zelph/HF route → governed revision-pinned live Wikidata. [SLR #28](https://github.com/chboishabba/slr/pull/28) owns recurrent acquisition; [SLR #10](https://github.com/chboishabba/slr/pull/10) owns the Nat statement bundle.
- [ITIR shared shard artifact](https://github.com/chboishabba/ITIR-suite/blob/main/itir-mcp/src/itir_mcp/shard_transport.py) validates `shared-shard-artifact/v1`; it is not identical by declaration to native Zelph `zelph-hf-layout/v2` or `v3`. Translate with explicit ABI evidence.
- [ITIR Zelph v1/v2 storage](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_hf_storage_contract_20260326.md) vs [v3 bucket proposal](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_hf_v3_shard_contract_20260326.md); use the later correction for section-global names and cache revalidation.
- [ITIR sharder/sink matrix](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_kant_zos_shard_contract_matrix_20260327.md): Zelph-style query sharding, Kant-style content-addressed packaging, HF/IPFS alternate sinks. Role fit is not proof of optimality.

## Decisive gates (Z4–Z10), all OPEN without fresh immutable-revision receipts

| Gate | Exact required evidence | Negative control |
|---|---|---|
| **Z4 — Same-artifact pinning** | Blessed Zelph commit, manifest URI+revision/ETag, shard tree+digest, route sidecar+digest, query/selector, graph revision; reject mixed-source snapshots | Patch manifest in place; ensure revalidation prevents use of stale source.binPath |
| **Z5 — Name-section identity** | Prove `nameOfNode`/`nodeOfName` section-global selector mapping agrees across binary index, manifest and direct read | Per-language index restart must fail |
| **Z6 — Direct transport** | Run pinned `run_zelph_partial_load_harness.py`; v2 meta/left/nameOfNode/nodeOfName direct shard reads, not sequential fallback; decode verified | Intentionally corrupt one shard and record hard failure, not passing fallback |
| **Z7 — Physical fetch budget** | Emit `remote_object_gets`, `bytes_fetched`, cache misses/hits, coalesced gets, live fallbacks and result counts for same QID/name workload; compare v2/v3 | Equal logical QID count but larger physical-object fan-out cannot pass bound |
| **Z8 — Query-family coverage** | Certified positive/negative coverage for *specific* P31/P279, exact-name, qualifier, sibling-period/target-family query with revision-scoped basis | Missing QID on partial shard must never become `novalue` or ontology contradiction |
| **Z9 — SLR cross-carrier replay** | Physical Zelph execution receipt → persisted SLR source-native candidate → S29 scoped review/ITIR packet → dependency-scoped reopening, with exact digests | Corrupt source, re-route to another revision, or change scope; reject |
| **Z10 — NORA replay** | Real NORA fixture maps `manual_search`/`modeling_gap` into existing bounded source route and returns a readable, non-promoting explanation of the coverage result | Review `valid` or `invalid` cannot itself trigger semantic promotion or live Wikidata edit |

### Narrowest maximum cut

**First establish Z4+Z5+Z6 on an actual current hosted publication.** Without the correct manifest/index/route identity and direct shard decode, the NORA→Zelph integration is only a producer plan. Then perform Z7 with the *same physical workload*, Z8 positive and negative controls, and Z9/Z10 native SLR/NORA replay.

There is **no need** to start with a new v3 builder or all 57,989 statements. If current v2 direct transport and same-object coverage pass, v3 is an efficiency optimisation. If v2 exceeds observed fetch budgets, benchmark v3 in parallel while keeping bounded Nat diagnostics functioning.

## Acceptance invocation

In an ITIR checkout with the real blessed Zelph executable, .bin/manifest and HF shard artifacts:

```sh
python tools/run_zelph_partial_load_harness.py --help
python tools/estimate_zelph_shard_fetch_budget.py --help
python -m pytest -q itir-mcp/tests/test_shard_transport.py
```

These commands are orientation/contract checks, **not** a claim of execution in this audit. Follow the pinned artifact and harness command fields from the [July checklist](https://github.com/chboishabba/ITIR-suite/blob/main/docs/planning/zelph_develop_sparql_partial_load_readiness_20260702.md); do not invent an executable or substitute a synthetic local manifest for canonical hosted acceptance.
