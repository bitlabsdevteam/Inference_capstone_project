#!/usr/bin/env bash
set -euo pipefail

SKIP_PREFLIGHT=0
REQUIRE_MODAL_AUTH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-preflight)
      SKIP_PREFLIGHT=1
      shift
      ;;
    --require-modal-auth)
      REQUIRE_MODAL_AUTH=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: scripts/validate_repo.sh [--skip-preflight] [--require-modal-auth]" >&2
      exit 2
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="python3"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  export PATH="$ROOT_DIR/.venv/bin:$PATH"
fi

echo "==> Bytecode check"
"$PYTHON_BIN" -m py_compile \
  starter_code/preflight_infertutor.py \
  starter_code/result_schema.py \
  starter_code/run_infertutor_experiment.py \
  starter_code/load_test_infertutor.py \
  starter_code/score_infertutor.py \
  starter_code/generate_submission_artifacts.py \
  tests/test_infertutor_tools.py

echo "==> Unit tests"
"$PYTHON_BIN" -m unittest tests.test_infertutor_tools

if [[ "$SKIP_PREFLIGHT" -eq 0 ]]; then
  echo "==> Preflight"
  PREFLIGHT_ARGS=(--json)
  if [[ "$REQUIRE_MODAL_AUTH" -eq 1 ]]; then
    PREFLIGHT_ARGS+=(--require-modal-auth)
  fi
  "$PYTHON_BIN" starter_code/preflight_infertutor.py "${PREFLIGHT_ARGS[@]}"
else
  echo "==> Preflight skipped"
fi

echo "Validation complete."
