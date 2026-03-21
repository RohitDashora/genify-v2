#!/usr/bin/env bash
# Create .venv-test at repo root and install tests/requirements-test.txt (Genify + pytest).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
elif command -v python3.12 &>/dev/null; then
  PY=python3.12
elif command -v python3.11 &>/dev/null; then
  PY=python3.11
elif command -v python3 &>/dev/null; then
  PY=python3
else
  echo "error: need python3.11+, python3.12, or set PYTHON=/path/to/python" >&2
  exit 1
fi

VER="$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Using: $($PY --version)"
if [[ "${VER%%.*}" -eq 3 ]] && [[ "${VER#*.}" -ge 13 ]]; then
  echo "warning: Python 3.13+ may lack wheels for some Genify deps; prefer 3.11 or 3.12 (set PYTHON=...)" >&2
fi
"$PY" -m venv .venv-test
.venv-test/bin/pip install -U pip
.venv-test/bin/pip install -r tests/requirements-test.txt
echo ""
echo "Test venv ready: .venv-test/"
echo "  ./scripts/run_tests.sh"
echo "  .venv-test/bin/python -m pytest tests/ -v"
