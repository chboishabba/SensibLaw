#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUPER_ROOT="$(cd "${ROOT}/.." && pwd)"
VENV_PYTHON="${SUPER_ROOT}/.venv/bin/python"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Expected superproject venv python at ${VENV_PYTHON}" >&2
  exit 1
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
cd "${ROOT}"
exec "${VENV_PYTHON}" -m pytest "$@"
