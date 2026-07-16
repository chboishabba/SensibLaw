# Repository Guidelines

## Project Structure & Module Organization
Python orchestration lives under `src/` (`sensiblaw`, `sensiblaw_streamlit`, `fastapi`, and `pydantic` packages) with shared utilities in `scripts/` and CLI-ready entry points in `sensiblaw/`. UI assets and experimental dashboards sit in `sensiblaw_streamlit/` and `ui/`, while legal corpora and fixtures reside in `data/` and `examples/`. Keep unit tests in the parallel `tests/` tree; reuse fixtures in `tests/fixtures/` and seeded payloads in `tests/templates/`. Design notes, automation walkthroughs, and deep dives belong in `docs/`.

## Required Reading
Before writing code, read:

- `README.md`
- `docs/itir_vs_sl.md`
- `docs/implementation_style_guide.md`

Do not start from generic Python repo habits alone. SensibLaw follows ITIR
style rules that prefer a generic data-in/world-model-out product surface and
treat lane modules as demos or compatibility shims.

Hard rules:

- If the module name already carries the lane or domain, public function names
  must stay generic: `build_report`, `build_case`, `build_contract`,
  `build_receipt`, `attach_receipt`, `load_fixture`, `load_records`.
- No lane owns a semantic method. All lanes must import the same generic
  extraction, follow, world-model, projection, and receipt machinery, then
  supply only profile defaults, source material, authority preferences, bridge
  targets, and outward labels.
- Do not expose lane names as the primary public API. Users should be able to
  provide data directly to the shared product surface:
  `build_world_model(data) -> project_*(world_model) -> attach_receipt(...)`.
- Do not add public lane/scenario selectors or adapter overrides such as
  `profile=...`, `kind=...`, or `adapter_hint=...` to that generic product
  surface. If a demo or compatibility wrapper still needs internal routing,
  keep it behind local wrapper metadata and out of the exported user-facing
  API.
- Historical lane modules such as `nat.py`, `au.py`, `gwb.py`, and `brexit.py`
  are demonstration or compatibility wrappers only. They must call the same
  generic product API that a downstream user can call.
- Distinguish lane family from profile/fixture selectors in arguments and docs.
  Use names like `profile`, `artifact`, or `selector`, not vague overloads that
  collapse lane and report identity together.
- Keep the distinction explicit in code and docs:
  `nat` is the lane family, while `climate_review_demonstrator`,
  `disjointness_report`, and `q43229_superclass_pressure` are profiles.
- Canonical demo surfaces must be zero-glue. Prefer `module.build_report()` or
  `module.load_fixture(profile=...)` over call chains that make callers wire
  input-loading steps by hand.
- Fixture loaders are not product capabilities. Shared SensibLaw modules must
  not expose lane-specific loaders such as `load_nat_fixture`,
  `load_gwb_fixture`, `load_au_fixture`, or `load_brexit_fixture` outside
  demos, tests, and compatibility wrappers.
- Treat `world model` as a receipt-free latent carrier, not as a truth oracle
  or a report synonym. Prefer the split:
  `build_world_model(...) -> project_report(...) -> attach_receipt(...)`.
- Keep the missing adapter layer explicit:
  `artifact -> world_model_adapters -> CandidateWorldModel`.
  Do not leave lane-local normalization semantics parked permanently in
  `au_world_model.py`, `gwb_narrative_world_model.py`, or similar wrappers.
- Prefer shared projections such as `project_report(...)`,
  `project_claim_table(...)`, `project_timeline(...)`,
  `project_review_surface(...)`, and `project_linkage_case(...)` before
  inventing a lane-local report or review surface.
- Before adding a new public helper, search for an existing generic workflow or
  adapter and extend that surface instead of introducing a lane-named callable.
- If a proposed public function name contains both the lane name and the
  operation, stop and refactor.
- If you encounter lane-specific adapters, node families, projection labels, or
  content that appears to own semantics another lane could also use, raise that
  to the user before extending it further. Do not silently deepen
  `gwb_*`, `au_*`, `brexit_*`, `nat_*`, `wikidata_*`, or similar semantics if
  the operation could live under a shared adapter, projection, or profile.
- When raising such a case, include:
  - the current lane-specific surface
  - why it is overindexed or non-portable
  - the likely generic owner, such as `world_model_adapters.py`,
    `world_model_projections.py`, `linkage_depth.py`,
    `linkage_case_inputs.py`, or a new shared adapter module if genuinely
    required by multiple lanes
  - the thinnest lane-profile wrapper that should remain afterward
- Treat lane-local terms such as actor, office, legal reference, review item,
  archive policy item, AU review fact, or GWB legal-follow queue item as
  profile metadata over shared carrier types unless the repo style guide proves
  otherwise.
- Shared capabilities should be preferred and named generically. Examples
  include: `SourceAnchor`, `TextUnit`, `DocumentUnit`, `NormalizedForm`,
  `PNFUnit`, `TaskCandidate`, `ClaimCandidate`, `EventCandidate`,
  `ThemeCandidate`, `RelationCandidate`, `FollowTarget`, `FollowEdge`,
  `AuthorityCandidate`, `AuthorityLineage`, `ExternalBridgeCandidate`,
  `ReviewSurface`, and `TrancheAnchor`.
- Follow, task/theme extraction, PNF-backed normalization, legal-follow,
  narrative-follow, authority lineage, and external joins are shared
  capabilities. A lane may configure or label them, but it must not redefine
  them as lane-owned primitives.

## Build, Test, and Development Commands
Create a virtual environment and install tooling: `pip install -e .[dev,test]`. Run `pytest` for the full Python test suite, and scope to modules with `pytest tests/streaming/test_versioned_store.py`. Format with `ruff format` and lint via `ruff check --fix`; run `ruff check --select I` if imports need sorting. Verify type coverage using `mypy .`. For dashboards, launch `streamlit run streamlit_app.py`. Invoke the CLI with `python -m sensiblaw.cli --help` when iterating locally.

## Coding Style & Naming Conventions
Target Python 3.11 features (match statements, typing.Annotated) while keeping modules import-safe for 3.10 fallback. Use 4-space indentation, descriptive snake_case for functions and variables, and PascalCase for Pydantic models and FastAPI routers. Keep module-level constants in UPPER_SNAKE_CASE, and prefer dependency injection over module globals. Format exclusively with Ruff to avoid churn, and ensure new modules expose a concise `__all__` where APIs are intended for reuse.

## Testing Guidelines
Co-locate unit tests next to their target modules within `tests/`, mirroring the package path. Name tests `test_<feature>.py` and favour descriptive `test_handles_multi_column_toc` style functions. Leverage Hypothesis strategies where coverage is critical, and patch outbound IO via `pytest-mock`. Run `pytest --maxfail=1 -q` before opening a PR and capture new failure modes with regression fixtures.

## Commit & Pull Request Guidelines
Follow the repository’s imperative commit style (`Improve multi-column TOC parsing`). Keep commits scoped to a logical change and document cross-cutting edits in the body if needed. Pull requests should include a crisp summary, linked issues, before/after notes for behaviour changes, and updated screenshots when UI surfaces change. Confirm CI passes locally (`pytest`, `ruff check`, `ruff format --check`) and note any skipped checks in the description.

## Regex & Parsing Guideline
Avoid using raw regex or importing raw spaCy, `src.text.*`, or `src.nlp.*` modules directly for text segmentation, sentence splitting, tokenization, or entity parsing unless absolutely necessary. Downstream policy and integration code must utilize the public `sensiblaw.interfaces` wrapper layer (specifically `parser_adapter` for parsing/segmentation and `shared_reducer` for token/span/reducer work).

Available interface functions:
- `parse_canonical_text`
- `tokenize_presemantic_text`
- `split_presemantic_text_segments`
- `tokenize_canonical_with_spans`
- `collect_canonical_relational_bundle`

Standard Python string methods (such as `.split()`, `.replace()`, `.strip()`) are preferred for simple layout/separator checks.
