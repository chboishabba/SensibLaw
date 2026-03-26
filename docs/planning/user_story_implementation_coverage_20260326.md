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
- First bounded protected-disclosure envelope support now exists:
  `scripts/build_protected_disclosure_envelope.py`,
  `src/fact_intake/protected_disclosure_envelope.py`,
  `tests/test_protected_disclosure_envelope.py`
  implement a metadata-only protected-disclosure artifact with forced
  local-only/do-not-sync handling, deny-by-default recipient behavior, and
  no fact-intake persistence/read-model sidecars.
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
- No dedicated chat-log/day-ingest pipeline for private users.
- No broad import adapter layer beyond the first bounded JSON/TextUnit-style
  handoff contract.
- No UI surface for redaction-first selective export.
- No full end-to-end path from live personal capture to scoped legal/clinical/
  advocacy/regulatory handoff; only the first fixture-backed artifact path
  exists.
- The first bounded target is now documented in:
  `docs/planning/personal_handoff_bundle_contract_20260326.md`

### Protected disclosure / workplace integrity
- A first metadata-only protected-disclosure envelope now exists.
- Still missing:
  - richer retaliation-aware export flavors beyond recipient allowlisting
  - whistleblower-specific live intake/import adapters
  - dedicated workflow/UI surfaces for workplace integrity cases

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
- a first metadata-only protected-disclosure envelope artifact with no
  fact-intake persistence sidecar
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

1. Personal/private day-to-escalation import plus scoped export.
2. SDK/API contract packaging for provenance-only integrators.
3. Community/disability intake and role-scoped service views.
4. Annotation/QA workbench over existing review queues.
5. Field inspection offline-first capture.
6. Research/lab-note adapters and publication export.
