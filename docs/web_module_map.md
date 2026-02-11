# SensibLaw Web/Streamlit Module Map (Current Implementation)

This is a concrete map of the **current** user-facing web surfaces in SensibLaw,
intended to help UI work (including future transitions) stay aligned with
backend contracts.

## Surface 1: Operations Console (Streamlit)

Launch:
- `streamlit run streamlit_app.py`

Entrypoints:
- `streamlit_app.py` (shim: adds `src/` to `sys.path`, calls `sensiblaw_streamlit.app:main`)
- `sensiblaw_streamlit/app.py` (page setup + tab router)

Tab modules (each exposes `render()`):
- Documents: `sensiblaw_streamlit/tabs/documents.py`
- Obligations: `sensiblaw_streamlit/tabs/obligations.py`
- Text & Concepts: `sensiblaw_streamlit/tabs/text_concepts.py`
- Knowledge Graph: `sensiblaw_streamlit/tabs/knowledge_graph.py`
- Case Comparison: `sensiblaw_streamlit/tabs/case_comparison.py`
- Collections (read-only diff): `sensiblaw_streamlit/tabs/collections.py`
- Ribbon: `sensiblaw_streamlit/tabs/ribbon.py`
- Utilities (labs/read-only): `sensiblaw_streamlit/tabs/utilities.py`

Shared UI utilities:
- Fixtures and fixture directory selection: `sensiblaw_streamlit/shared.py`
  - Supports query-param and env-var fixture selection (example: `?graph_fixture=...`)
  - Includes forbidden-term scanning to prevent semantic overreach in fixture-driven UI output
- Document preview helpers (includes embedded HTML via Streamlit components):
  `sensiblaw_streamlit/document_preview.py`

UI contract note:
- The console is a **thin orchestrator** over `src/` modules (ingest, graph, rules,
  receipts, storage). When UI work needs a new field or view, prefer adding it
  to an explicit payload/data structure in `src/` rather than “just formatting”
  opaque dicts inside Streamlit.

## Surface 2: Review UI (Streamlit, read-only bundle inspector)

Launch (from repo root):
- `streamlit run ui/app.py`

Entrypoint:
- `ui/app.py` (loads a review bundle JSON and renders read-only panels)

Panel modules:
- `ui/panels/obligations.py`
- `ui/panels/activation.py`
- `ui/panels/topology.py`
- `ui/panels/audit.py`

Intended use:
- Human inspection of a review bundle payload (no mutation, no reasoning).

## Surface 3: API (web-facing but not a UI)

FastAPI routes live under:
- `src/api/`
- `src/server/`

This surface is used for programmatic access and UI integration, but it is not
the Streamlit UI itself.

