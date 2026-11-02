# Kitzerow chart — native external ontology bridge (2026-11-02)

This is a thin domain adapter onto SensibLaw's existing generic world-model and external ontology carriers. No new ontology authority, semantic compiler, S29 store, PostgreSQL schema, source parser or public editor is introduced.

## Original source and attribution

Kimberly Kitzerow, *BH4/Folate/Cobalamin/Homocysteine Pathway*, ResearchGate publication 377218425 (listed January 2024):
https://www.researchgate.net/publication/377218425_BH4FolateCobalaminHomocysteine_Pathway .
The available page reports a separate full-text upload on 2025-08-08. It declares CC BY-NC-ND 4.0. We record publicly displayed Rhea identifiers and source coordinates only, not her copyrighted chart. Her official research page https://www.kimberlyedu.org/researchgate-papers identifies the complete underlying network as proprietary. Neither complete historic binary/geometry nor whole network size is independently known.

Creator-specific selection, organization and proposed causal mechanisms belong to Kitzerow. The curated underlying Rhea reaction chemistry belongs to Rhea and primary biochemical researchers. Independent Reactome, ChEBI, UniProt, GO and other external ontology definitions retain their owners. Native bridge/projection and diagnostics are local SensibLaw/DASHI implementation work, not creator-authored software or new biological proof.

## Reused code and user stories

- src/policy/external_graph_bridge.py — generic revision-bound graph views, external bridge candidates, diagnostic pressure.
- src/policy/world_model.py — generic CandidateWorldModel.
- src/policy/world_model_projections.py — original read-only review projection.
- src/policy/linkage_adapters.py and linkage_depth.py — source -> typed candidate -> external -> review -> tranche.
- docs/external_graph_bridge.md and docs/external_ontologies.md — advisory external IDs vs own authority.
- ITIR-suite docs/planning/generic_world_model_compiler_convergence_20260716.md and docs/planning/linkage_adapter_kit_20260704.md — generic compiler, thin source adapters only.
- ITIR-US-17 and WIKI-US-01–04 — source context, bounded follow, review-before-edit and provenance.

Call src.policy.kitzerow_bh4_chart_adapter.build_world(chart, matrix) on two existing DASHI inputs:
docs/biology/KitzerowPublishedRheaChartObservedIndex.v1.json and
artifacts/biology/bh4-stoichiometric-matrix.json.

The output is a native sl.candidate_world_model.v0_1 with its ordinary review projection and linkage fragment, not another bio-specific graph engine.

The adapter also accepts an optional creator-selected Rhea curator receipt:
    
    build_world(chart, matrix, creator_reactions=creator_rhea_certificate)

DASHI obtains this receipt by reusing its existing Rhea REST/SPARQL
acquisition with the option --from-source-chart. The adapter validates
the exact creator selection, source index SHA-256 shape, acquired/failed
reaction accounting, Rhea source revision reference and each acquired
Rhea REST/SPARQL SHA-256. It adds a **separately scoped incomplete**
Rhea graph view and Rhea-curated ChEBI participant attachments using the
existing generic external bridge. It never manufactures a common
cellular pool or calls the source author's proposal a curated Rhea
reaction. A partial curator acquisition remains explicitly incomplete.
The retrieved Rhea live API release must be separately verified;
acquisition-time receipts are not release certificates.

Focused tests:
    
    python -m pytest tests/test_kitzerow_bh4_chart_adapter.py tests/test_kitzerow_rhea_receipt_bridge.py -q
 The comparison reports exact literal Rhea ID intersection and symmetric difference. It retains an unknown total size for Kitzerow's entire proprietary network. The graph coverage state is incomplete. Bridge candidates are review_required; physical-context pressure is abstain. Identifier overlap does not pay enzyme isoform, compartment, biological rate or proposed clinical causality.

Reactome already publishes SBML L3 and BioPAX L3 plus UniProt/ChEBI mapping downloads: https://reactome.org/download-data . Reuse those source-release and context-pinned standard exports rather than implementing full pathway standards from scratch.

## Exact remaining obligations

K-CHART-01 Acquire original chart/PDF bytes with rights, revision digest and image geometry (not completed).
K-CHART-02 Transcribe all publicly available reactions with author/source passage and preexisting reaction ownership (partial source-observed IDs only).
K-CHART-03 Pin Rhea, Reactome, UniProt, ChEBI, GO, KEGG, MetaCyc revisions, mapping predicates and context; do not infer same-object equivalence.
K-CHART-04 Use the existing native SLR INGEST-1/S29 and ITIR bounded source/graph receipt; any Dioxus read model is downstream, not built here.
K-CHART-05 Supply tissue/isoform/compartment/time-matched enzyme kinetics and exchanges; ontology cannot pay missing physical quantities.
K-CHART-06 Verify exact-head native Python/Agda kernel; reconcile stacked PRs against master. No source-written tests count as independently executed proof.

Focus:
python -m pytest tests/test_kitzerow_bh4_chart_adapter.py -q

No test execution, live source authentication, PostgreSQL acceptance, public ontology edit, or clinical conclusion is claimed by this connector workflow.
