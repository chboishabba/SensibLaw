# Repository Guidelines

## Project Structure & Module Organization
Python orchestration lives under `src/` (`sensiblaw`, `sensiblaw_streamlit`, `fastapi`, and `pydantic` packages) with shared utilities in `scripts/` and CLI-ready entry points in `sensiblaw/`. UI assets and experimental dashboards sit in `sensiblaw_streamlit/` and `ui/`, while legal corpora and fixtures reside in `data/` and `examples/`. Keep unit tests in the parallel `tests/` tree; reuse fixtures in `tests/fixtures/` and seeded payloads in `tests/templates/`. Design notes, automation walkthroughs, and deep dives belong in `docs/`.

## Build, Test, and Development Commands
Create a virtual environment and install tooling: `pip install -e .[dev,test]`. Run `pytest` for the full Python test suite, and scope to modules with `pytest tests/streaming/test_versioned_store.py`. Format with `ruff format` and lint via `ruff check --fix`; run `ruff check --select I` if imports need sorting. Verify type coverage using `mypy .`. For dashboards, launch `streamlit run streamlit_app.py`. Invoke the CLI with `python -m sensiblaw.cli --help` when iterating locally.

## Coding Style & Naming Conventions
Target Python 3.11 features (match statements, typing.Annotated) while keeping modules import-safe for 3.10 fallback. Use 4-space indentation, descriptive snake_case for functions and variables, and PascalCase for Pydantic models and FastAPI routers. Keep module-level constants in UPPER_SNAKE_CASE, and prefer dependency injection over module globals. Format exclusively with Ruff to avoid churn, and ensure new modules expose a concise `__all__` where APIs are intended for reuse.

## Testing Guidelines
Co-locate unit tests next to their target modules within `tests/`, mirroring the package path. Name tests `test_<feature>.py` and favour descriptive `test_handles_multi_column_toc` style functions. Leverage Hypothesis strategies where coverage is critical, and patch outbound IO via `pytest-mock`. Run `pytest --maxfail=1 -q` before opening a PR and capture new failure modes with regression fixtures.

## Commit & Pull Request Guidelines
Follow the repository’s imperative commit style (`Improve multi-column TOC parsing`). Keep commits scoped to a logical change and document cross-cutting edits in the body if needed. Pull requests should include a crisp summary, linked issues, before/after notes for behaviour changes, and updated screenshots when UI surfaces change. Confirm CI passes locally (`pytest`, `ruff check`, `ruff format --check`) and note any skipped checks in the description.
