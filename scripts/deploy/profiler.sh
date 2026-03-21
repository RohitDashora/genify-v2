#!/usr/bin/env bash
# shellcheck shell=bash
# MCP Profiler app — runs after UC functions.
# Stages a clean tree: NEVER upload .venv (uv run creates ~60MB+ wheels; snapshot limit 10MB/file).

deploy_profiler_app() (
    set -euo pipefail

    echo ""
    echo "==> Deploying MCP Profiler app '$PROFILER_APP'..."

    local PROFILER_PATH="${WORKSPACE_BASE}/${PROFILER_APP}"

    STAGING=$(mktemp -d)
    # shellcheck disable=SC2064
    trap 'rm -rf "${STAGING}"' EXIT

    if command -v rsync >/dev/null 2>&1; then
        rsync -a \
            --exclude='.venv' \
            --exclude='__pycache__' \
            --exclude='.pytest_cache' \
            --exclude='.mypy_cache' \
            --exclude='.ruff_cache' \
            --exclude='*.pyc' \
            --exclude='.DS_Store' \
            "${SCRIPT_DIR}/src/mcp-profiler/" "${STAGING}/"
    else
        cp -R "${SCRIPT_DIR}/src/mcp-profiler/." "${STAGING}/"
        rm -rf "${STAGING}/.venv" 2>/dev/null || true
        find "${STAGING}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
        find "${STAGING}" -name "*.pyc" -delete 2>/dev/null || true
    fi
    find "${STAGING}" -name ".DS_Store" -delete 2>/dev/null || true

    echo "    Staged $(find "${STAGING}" -type f | wc -l | tr -d ' ') files (excluded .venv, caches)"

    "${CLI[@]}" workspace import-dir "${STAGING}" "${PROFILER_PATH}" \
        --overwrite 2>&1 | tail -3

    if "${CLI[@]}" apps get "$PROFILER_APP" -o json &>/dev/null; then
        echo "    App exists."
    else
        echo "    Creating app..."
        "${CLI[@]}" apps create "$PROFILER_APP" \
            --description "FastMCP server for table data profiling" \
            --no-compute --no-wait
        sleep 3
    fi

    echo "    Updating resource bindings..."
    # Resource name sql_warehouse must match src/mcp-profiler/app.yaml valueFrom: sql_warehouse
    local PROFILER_SPEC
    PROFILER_SPEC=$(
        WAREHOUSE_ID="${WAREHOUSE_ID:-}" "$PYTHON" -c "
import json, os
wh = (os.environ.get('WAREHOUSE_ID') or '').strip()
sql_wh = {'permission': 'CAN_USE'}
if wh:
    sql_wh['id'] = wh
body = {
    'description': 'FastMCP server for table data profiling',
    'resources': [{'name': 'sql_warehouse', 'sql_warehouse': sql_wh}],
}
print(json.dumps(body))
"
    )
    if ! "${CLI[@]}" apps update "$PROFILER_APP" --json "$PROFILER_SPEC" -o json 2>&1; then
        echo "ERROR: apps update failed for $PROFILER_APP. Fix resource JSON or bind sql_warehouse in the Apps UI."
        exit 1
    fi

    echo "    Deploying..."
    "${CLI[@]}" apps deploy "$PROFILER_APP" --source-code-path "$PROFILER_PATH" --no-wait
    echo "    Profiler deployment initiated."
)
