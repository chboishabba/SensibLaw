#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${1:-demo-1}"
OUT_DIR="${2:-/tmp/qg-unification-stage2}"
DRY_RUN="${3:-}"

BRIDGE_DB="$OUT_DIR/qg_unification.sqlite"
ITIR_DB="$OUT_DIR/itir.sqlite"

mkdir -p "$OUT_DIR"

echo "[qg_unification] bridge: generating staged run ${RUN_ID}"
PYTHONPATH=. python SensibLaw/scripts/qg_unification_stage2_bridge.py \
  --run-id "$RUN_ID" \
  --out-dir "$OUT_DIR" \
  --db-path "$BRIDGE_DB"

touch "$ITIR_DB"

echo "[qg_unification] itir read-model: dry-run"
PYTHONPATH=. python SensibLaw/scripts/qg_unification_to_itir_db.py \
  --run-id "$RUN_ID" \
  --bridge-db "$BRIDGE_DB" \
  --itir-db "$ITIR_DB" \
  --dry-run

echo "[qg_unification] capture: dry-run"
PYTHONPATH=. python SensibLaw/scripts/qg_unification_to_tirc_capture_db.py \
  --run-id "$RUN_ID" \
  --bridge-db "$BRIDGE_DB" \
  --itir-db "$ITIR_DB" \
  --dry-run

if [[ "$DRY_RUN" == "--dry-run" ]]; then
  echo "[qg_unification] dry-run complete"
  exit 0
fi

echo "[qg_unification] itir read-model: persist"
PYTHONPATH=. python SensibLaw/scripts/qg_unification_to_itir_db.py \
  --run-id "$RUN_ID" \
  --bridge-db "$BRIDGE_DB" \
  --itir-db "$ITIR_DB"

echo "[qg_unification] capture: persist"
PYTHONPATH=. python SensibLaw/scripts/qg_unification_to_tirc_capture_db.py \
  --run-id "$RUN_ID" \
  --bridge-db "$BRIDGE_DB" \
  --itir-db "$ITIR_DB"

echo "[qg_unification] done"
