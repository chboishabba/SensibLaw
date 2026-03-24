#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "$REPO_ROOT"

echo "[qg_unification] run: valid payload"
PYTHONPATH=. python SensibLaw/scripts/qg_unification_smoke.py --json-file SensibLaw/tests/fixtures/qg_unification/da51_valid_demo.json

echo

echo "[qg_unification] run: invalid payload"
if ! PYTHONPATH=. python SensibLaw/scripts/qg_unification_smoke.py --json-file SensibLaw/tests/fixtures/qg_unification/da51_invalid_short_exponents.json; then
  echo "[qg_unification] invalid path behaved as expected"
fi
