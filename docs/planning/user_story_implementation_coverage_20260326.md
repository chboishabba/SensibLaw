# User Story Implementation Coverage

Date: 2026-03-26

Purpose: distinguish story coverage from implementation coverage so the repo is
clear about which use cases already have tested code paths and which remain
design pressure only.

## Implemented enough to claim repo-backed support

### Review-geometry lanes
- AU affidavit coverage review:
  `scripts/build_affidavit_coverage_review.py`,
  `tests/test_affidavit_coverage_review.py`,
  `tests/test_au_affidavit_coverage_review.py`,
  `tests/test_au_dense_affidavit_coverage_review.py`
- Wikidata checked/dense structural review:
  `scripts/build_wikidata_structural_review.py`,
  `scripts/build_wikidata_dense_structural_review.py`,
  `tests/test_wikidata_structural_review.py`,
  `tests/test_wikidata_dense_structural_review.py`
- GWB checked/broader review:
  `scripts/build_gwb_public_review.py`,
  `scripts/build_gwb_broader_review.py`,
  `tests/test_gwb_public_review.py`,
  `tests/test_gwb_broader_review.py`

### Shared comparison/reporting layer
- Normalized cross-lane metrics and profile mapping:
  `scripts/review_geometry_normalization.py`,
  `scripts/review_geometry_profiles.py`,
  `scripts/build_review_geometry_normalized_summary.py`,
  `tests/test_review_geometry_normalized_summary.py`,
  `tests/test_review_geometry_profiles.py`
- Deterministic review artifacts and markdown summaries:
  candidate/provisional rows, bundles, normalized metrics, and replayable
  fixture outputs exist across AU, Wikidata, and GWB review lanes.

### Partial-stack support that exists but is narrower than the stories
- First bounded personal/private handoff support now exists:
  `scripts/build_personal_handoff_bundle.py`,
  `src/fact_intake/personal_handoff_bundle.py`,
  `tests/test_personal_handoff_bundle.py`
  implement a CLI/artifact-first path from bounded personal entries to
  recipient-scoped lawyer/doctor/advocate/regulator export with explicit
  exclusions, redaction markers, local-only/do-not-sync flags, and preserved
  review/operator views.
- First bounded chat/day ingest adapter now exists:
  `scripts/build_personal_handoff_from_chat_json.py`,
  `src/fact_intake/personal_chat_import.py`,
  `tests/test_personal_chat_import.py`
  normalize bounded chat/day JSON into either the personal handoff input
  contract or the metadata-only protected-disclosure envelope contract.
- First repo-local DB-backed ingest adapter now exists:
  `scripts/build_personal_handoff_from_message_db.py`,
  `tests/test_personal_message_db_import.py`
  reuse `chat_test_db` / `messenger_test_db` loaders to feed the same
  handoff/envelope contracts without hand-authoring entry rows.
- First real export-backed ingest seam now exists:
  `scripts/build_personal_handoff_from_openrecall.py`,
  `tests/test_personal_openrecall_import.py`
  reuse imported `openrecall_capture` units from the ITIR/OpenRecall bridge to
  feed the same handoff/envelope contracts.
- First direct Messenger/Facebook export-backed ingest adapter now exists:
  `scripts/build_personal_handoff_from_messenger_export.py`,
  `src/fact_intake/messenger_export_import.py`,
  `tests/test_personal_messenger_export_import.py`
  accept bounded `message_1.json`-style Messenger export inputs directly,
  filter obvious system/noise rows, preserve the current privacy boundary, and
  feed the same handoff/envelope contracts without routing through an
  intermediate sample DB.
- First anonymous Google public-source adapters now exist:
  `scripts/build_personal_handoff_from_google_public.py`,
  `src/fact_intake/google_public_import.py`,
  `tests/test_google_public_import.py`
  accept public Google Docs and Sheets links anonymously, normalize them into
  `TextUnit` rows, and feed the same handoff/envelope contracts.
- First contested-narrative Google Docs comparison surface now exists:
  `scripts/build_google_docs_contested_narrative_review.py`,
  `tests/test_google_docs_contested_narrative_review.py`
  extract affidavit text from one public Google Doc, normalize the responding
  Google Doc into `fact.intake` rows, and compare them through the existing
  affidavit-coverage review surface.
- First bounded protected-disclosure envelope support now exists:
  `scripts/build_protected_disclosure_envelope.py`,
  `src/fact_intake/protected_disclosure_envelope.py`,
  `tests/test_protected_disclosure_envelope.py`
  implement a metadata-only protected-disclosure artifact with forced
  local-only/do-not-sync handling, deny-by-default recipient behavior,
  disclosure-route gating, identity-minimization controls, and no fact-intake
  persistence/read-model sidecars.
- Provenance/receipt-bearing exports are real:
  review artifacts carry stable ids, bundle rows, source references, and
  normalized summaries suitable for downstream consumption.
- Provenance-only partner/integrator use is partially supported:
  deterministic JSON and summary exports exist, but there is no separate SDK
  or contract package yet.
- Offline-first capture exists only in a narrow bridge sense:
  `scripts/qg_unification_to_tirc_capture_db.py` and related fixtures prove a
  capture sink exists, but not a general-purpose offline field workflow.

## Story families that are still aspirational or only partially covered

### Personal/private escalation
- No broad live chat-log/day-ingest pipeline for private users.
- A first bounded chat/day JSON adapter and a repo-local sample-DB adapter now
  exist, and the first real export-backed sources are now wired through
  OpenRecall, a bounded direct Messenger export adapter, and first anonymous
  Google public-source adapters; broader live/export-backed ingest is still
  missing beyond those seams.
- No UI surface for redaction-first selective export.
- No full end-to-end path from live personal capture to scoped legal/clinical/
  advocacy/regulatory handoff; the current path is still bounded and
  fixture-first.
- The first bounded target is now documented in:
  `docs/planning/personal_handoff_bundle_contract_20260326.md`

### Protected disclosure / workplace integrity
- A first metadata-only protected-disclosure envelope now exists.
- The envelope now includes a first retaliation-aware control layer:
  disclosure-route gating and identity-minimization modes above the original
  recipient allowlist.
- Still missing:
  - whistleblower-specific live intake/import adapters
  - dedicated workflow/UI surfaces for workplace integrity cases
  - broader workflow semantics beyond the current route/minimization controls

### Community / disability / advocacy workflows
- No tailored intake schema for support organizations.
- No role-scoped views beyond generic summary/export artifacts.
- No advocacy-oriented pattern/episode aggregation workflow.

### Annotation / QA
- No annotator workbench.
- No explicit abstain/inter-rater workflow UI.
- Only the lower-level review queue primitives exist.

### Education / research capture to publication
- No research/lab-note importer.
- No publication-safe export layer tuned for citations/exclusions.
- Could reuse capture/export patterns, but adapters do not exist yet.

### Field safety / inspection
- No photo/checklist capture pipeline.
- No inspection-specific absence/sync metadata.
- No regulator/insurer export contract for field inspections.

### SDK / API integrator experience
- No published SDK surface.
- No explicit machine-readable contract docs for embedded provenance use.
- Exports are deterministic, but integrator-facing packaging is still implicit.

## Current honest claim boundary

The repo can honestly claim:
- tested review-geometry and provenance-bearing comparison/reporting for AU,
  Wikidata, and GWB
- deterministic artifact generation with normalized cross-lane metrics
- a first bounded personal handoff artifact path with scoped export and
  explicit exclusions/redactions
- a first bounded chat/day JSON adapter into the personal handoff and
  protected-envelope artifact lanes
- a first repo-local DB-backed ingest seam into the same lanes
- first export-backed ingest seams through imported OpenRecall captures and a
  bounded direct Messenger/Facebook export adapter
- first anonymous Google Docs/Sheets public-source adapters into the same
  lanes
- a first contested-narrative Google Docs comparison surface over the existing
  affidavit-coverage review lane
- a first metadata-only protected-disclosure envelope artifact with no
  fact-intake persistence sidecar and a first retaliation-aware control layer
- bounded partner/integrator support through stable exports

The repo should not yet claim:
- complete private-user workflow support
- full whistleblower/protected-disclosure product support
- disability/community-service operational support
- annotation workbench support
- research-publication tooling
- field inspection/offline capture productization
- SDK-grade integrator experience

## Priority order if implementation should follow the stories

1. Richer live/export-backed chat/day ingest adapters beyond the current
   bounded JSON, repo-local sample-DB, direct Messenger-export, anonymous
   Google public-source, and first OpenRecall-backed seams.
2. SDK/API contract packaging for provenance-only integrators.
3. Community/disability intake and role-scoped service views.
4. Annotation/QA workbench over existing review queues.
5. Field inspection offline-first capture.
6. Research/lab-note adapters and publication export.
