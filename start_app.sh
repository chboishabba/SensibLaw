#!/bin/bash
set -euo pipefail

ROOT="$(cd -- "$(dirname "$0")" && pwd)"
export SENSIBLAW_GRAPH_FIXTURE="${SENSIBLAW_GRAPH_FIXTURE:-$ROOT/tests/fixtures/ui/knowledge_graph_docs.json}"
export SENSIBLAW_FORCE_GRAPH_FIXTURE="${SENSIBLAW_FORCE_GRAPH_FIXTURE:-$SENSIBLAW_GRAPH_FIXTURE}"
export SENSIBLAW_UI_FIXTURE_DIR="${SENSIBLAW_UI_FIXTURE_DIR:-$ROOT/tests/fixtures/ui}"

python3 -m venv "$ROOT/venv"
source "$ROOT/venv/bin/activate"
git pull
pip install -r "$ROOT/requirements.txt"
streamlit run "$ROOT/streamlit_app.py"
