#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

OUT_DIR="${1:-/tmp/qg-unification-stage2}"
RUN_ID="${QG_UNIFICATION_RUN_ID:-fixture-demo-1}"
DB_PATH="${OUT_DIR}/qg_unification.sqlite"
PAYLOAD="SensibLaw/tests/fixtures/qg_unification/da51_valid_demo.json"

cd "$REPO_ROOT"

echo "[qg_unification] stage2 fixture replay"
PYTHONPATH=. python SensibLaw/scripts/qg_unification_stage2_bridge.py \
  --json-file "$PAYLOAD" \
  --run-id "$RUN_ID" \
  --out-dir "$OUT_DIR" \
  --db-path "$DB_PATH"

echo
echo "[qg_unification] artifact: ${OUT_DIR}/qg_unification_run_${RUN_ID}.json"
echo "[qg_unification] db: ${DB_PATH}"
