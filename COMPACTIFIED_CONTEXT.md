# COMPACTIFIED_CONTEXT

## Purpose
Compact snapshot of intent while applying the get-shit-done and update-docs-todo-implement workflows for S7–S9 execution.

## Objective
Close S7–S9 (TextSpan authority, cross-doc topology v2, read-only UI) with docs/TODO sequencing and deterministic tests.

## Near-term intent
- Preserve span authority and read-only surfaces; do not add reasoning or compliance logic.
- Keep Layer 3 regeneration deterministic and promotion gates auditable.

## Completed prior milestones
- Sprint S5: actors, actions/objects, scopes, lifecycle, graph projection, stability hardening — shipped and flag-gated.
- Sprint S6: query API, explanation surfaces, projections, alignment, schema stubs, and guard review completed; no-reasoning contract enforced.
- Sprint S7: TextSpan contract + Layer 3 enforcement for rule atoms/elements.
- Sprint S8: non-judgmental cross-doc topology (`obligation.crossdoc.v2`).
- Sprint S9: read-only UI hardening (fixtures, Playwright smoke, obligations tab).

## Milestone scope
- Deliver read-only, deterministic surfaces over the existing normative lattice: queries, explanations, alignment, projections, schemas.
- Keep LT-REF, CR-ID/DIFF, OBL-ID/DIFF, and provenance invariants frozen; no compliance or interpretive behavior.

## Dependencies / infra constraints
- None new; spaCy/Graphviz/SQLite remain the baseline.

## Assumptions
- Python 3.11 target with 3.10 fallback; Ruff formatting.
- Clause-local, text-derived extraction; no cross-clause inference.

## Recent decisions (2026-02-06)
- Canonical TextSpan model added (`revision_id`, `start_char`, `end_char`) and persisted on rule atoms/elements.
- Promotion receipts now carry span IDs; signals block promotion on overlap.
- Cross-doc topology upgraded to `obligation.crossdoc.v2` with `repeals/modifies/references/cites`.
- Read-only UI hardened: obligations tab, fixture payloads, and forbidden-language guard.
- Multi-modal doctrine + human tools integration captured for ITIR/SensibLaw.
- docTR profiling notes captured for SensibLaw root PDFs (pdfminer: 515 pages, 1,623,269 chars) with a follow-up timing run scheduled for 2026-02-06.

## Open questions
- Do we need richer fixtures for multi-verb phrases or nested scopes as we exercise S6 queries/views?
- Which consumers (CLI, API, Streamlit) should receive the first query/explanation surface?
- How should alignment reports surface metadata deltas without touching identity? (to be defined in S6.3)

## Chat mention scan (2026-02-03)
Ranked conversations by total mention frequency of: `SL`, `sensiblaw`, `ITIR`, `tircorder`, `tirc`.
Full ranking saved at `__CONTEXT/last_sync/mentions_rank_20260203_225730.tsv`.
Top 10 by total hits:
- 721 hits, 82 msgs: SENSIBLAW (thread `4d535d3f33f54b1040ab38ec67f8f550a0f69dce`)
- 637 hits, 49 msgs: Taxonomising legal wrongs (thread `74f6d0e08de82556df95c6ab1edb51557fede4fa`)
- 546 hits, 51 msgs: Feature timeline visualization (thread `f8170d36e0b2c28b2bb0366a7dc35a433e26ca00`)
- 308 hits, 22 msgs: Expand explanation request (thread `df662e5df0a444fa97e57053dd7c1cec130f9aeb`)
- 194 hits, 10 msgs: Data management ontology topology (thread `331a7d1304f329259315649e7a9d729a83b51daf`)
- 191 hits, 14 msgs: Aptos cryptocurrency overview (thread `32c691e2032f3ed787499254720081202500e94b`)
- 184 hits, 16 msgs: Actor table design (thread `21f55daa80206517e38f8c0fa56ee9bb2db8a9a0`)
- 163 hits, 15 msgs: Summary of key details (thread `cfacd6488919ade801d8137a9d05573ec31f9345`)
- 149 hits, 34 msgs: Research paper development (thread `15567e0112f953179e2ef6571de023b415d68bbb`)
- 141 hits, 23 msgs: Category coverage review (thread `83ee7436aa909dd31a14a147f10bb78cd52b6f55`)
Walkthrough notes saved at `__CONTEXT/last_sync/mentions_top10_walkthrough_20260203_230500.md`.
Quick walkthrough (top 10):
- SENSIBLAW: high-volume planning around ingesting/viewing Australian law, with explicit SL/ITIR/TiRCorder references.
- Taxonomising legal wrongs: ontology/taxonomy debate; TiRCorder and SL/ITIR framing recur as design anchors.
- Feature timeline visualization: README/vision work tying TiRCorder timeline views to SL/ITIR context.
- Expand explanation request: glossary/atom concepts, explanation surfaces, and actor/sentence-view needs.
- Data management ontology topology: distillation of ontology/topology spine for TiRC + SensibLaw integration.
- Aptos cryptocurrency overview: positioning SensibLaw/TiRC in institutional data/API/market comparisons.
- Actor table design: schema guidance on actors table boundaries and identity modeling.
- Summary of key details: competitive/positioning summaries, with SL vs others framing.
- Research paper development: steering research paper gaps and TiRCorder/ITIR priorities.
- Category coverage review: ML/graph category fit for SensibLaw/TiRCorder stack.
Selected walkthroughs (ranks 11, 14, 16-42, 44, 60, 67, 71-74, 78-81, 84-85):
- 11 Gary's YouTube strategy: SensibLaw feature-to-video mapping and marketing pipeline.
- 14 House v The King principles: PDF-to-principles/graph pipeline framed for SensibLaw/TiRCorder.
- 16 Timeline stream roadmap issue: coherence issues in timeline roadmap and prior rewrite log.
- 17 PDF to TiRCorder integration: integrating specific PDFs into TiRCorder pass.
- 18 SL Formalism Interpretation and Projection: formalism framing tied back to SensibLaw goals.
- 19 Design spec creation: request for developer-facing SensibLaw design spec.
- 20 Debates on causality: cross-domain debate/theory mapping with intermittent SL/TiRC framing.
- 21 Legal practice highlights: legal-practice relevance and SensibLaw burnout assistance.
- 22 Postgres vs alternatives for Rust: database choice rationale for SensibLaw stack.
- 23 Contributors needed for TiRCorder: project origin story and system coherence framing.
- 24 CI workflow optimization: GitHub Actions fixes for SensibLaw.
- 25 Key points summary: Wikitology summary with SL/TiRC reflection prompt.
- 26 Legal ethics and systems: legal-ethics discussion and briefing.
- 27 Oracle WHS compliance tool: comparison query referencing SensibLaw.
- 28 Ternary packing optimization: dashifine/ternary math discussion with SL/TiRC mentions.
- 29 Print principles list: PDF/JSON refinement plan for SensibLaw atoms.
- 30 Open-source contract analysis: SensibLaw positioned vs commercial contract tools.
- 31 Connect Codex to CDT: Codex CLI + Chrome DevTools connectivity.
- 32 TiRCorder goal summary: goal/acceptance bullets for rights-first TiRCorder.
- 33 Coles Palantir usage query: Palantir/system discussion with SL/TiRC mentions.
- 34 Balanced ternary systems: many-valued logic lineage tied to SensibLaw semantics.
- 35 Cannabis reforms Australia 2026: mixed content with incidental SL/TiRC mentions.
- 36 Table of contents processing: task backlog references for SensibLaw atom normalization.
- 37 Bitcoin value vs price drop: political-economic mapping with SL/TiRC ontology angle.
- 38 Key torts in Australia: tort taxonomy coverage with SL/TiRC references.
- 39 Boundary layer in law: boundary-layer framing for SensibLaw context.
- 40 Markdown table conversion: generic conversion task with SensibLaw mentions.
- 60 Taylor Swift politics: cultural critique + essay framing with SL/TiRC mentions.
- 67 Huawei patent explanation: ternary encoding note with SL/TiRC references.
- 71 Analyze FAQyMe Gene: request for direction on a pasted artifact mentioning SL/TiRC.
- 72 Idempotence and normalisation: spreadsheet + normalization note with SL/TiRC references.
- 73 Materialism vs Dialectics: brief context mention of ITIR.
- 78 StatiBaker Proposal: assistant concept spanning ITIR products and daily workflow.
- 79 OCR extraction and categorization: OCR extraction summary with SensibLaw mention.
- 80 Timeline prototype description: timeline prototype notes with ITIR mention.
- 85 Test computational efficiency: dashifine performance bottleneck note with SensibLaw mention.
Intersections with roadmap/todo/readme (2026-02-03):
- Repo `README.md`: submodule map matches chats spanning SensibLaw, SL-reasoner, TiRCorder, and WhisperX; the YouTube/roadmap/timeline threads align with cross-submodule integration framing.
- `ROADMAP.md`: focus on deterministic chat-history ingest into SQLite with SL/TIRC views overlaps with threads about ingest, explanation surfaces, timeline visualization, and cross-thread analysis.
- `SensibLaw/README.md`: shared TiRC + SensibLaw layered architecture aligns with ontology/taxonomy, actor table, PDF-to-graph, and timeline/claims discussions.
- `SensibLaw/todo.md`: S6 read-only deterministic surfaces and ingestion discipline align with explanation/trace requests, PDF integration, CI hardening, and schema/guardrail emphasis in the chats.

## Sources
Chat-sourced statements are now referenced from the compression/ITIR overlay
discussion (see `698218f7-9ca4-83a1-969d-0ffc3d6264e4:1-80`).
Use `CONVERSATION_ID:line#` citing the line-numbered excerpts in
`__CONTEXT/last_sync/`.
