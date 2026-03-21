#!/usr/bin/env bash
# Run Python tests using .venv-test (create with ./scripts/setup_test_venv.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv-test/bin/python ]]; then
  echo "error: .venv-test missing or broken. Run: ./scripts/setup_test_venv.sh" >&2
  exit 1
fi

RUNNER="${TEST_RUNNER:-unittest}"
if [[ "$RUNNER" == "pytest" ]]; then
  exec .venv-test/bin/python -m pytest tests/ -v "$@"
else
  exec .venv-test/bin/python -m unittest discover -s tests -p 'test_*.py' -v "$@"
fi
