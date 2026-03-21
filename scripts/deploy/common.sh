#!/usr/bin/env bash
# shellcheck shell=bash
# Shared helpers for deploy.sh — sourced by deploy.sh (do not run directly).

deploy_resolve_python() {
    PYTHON="python3"
    if ! python3 -c "import yaml" 2>/dev/null; then
        if [ -x "${SCRIPT_DIR}/.venv/bin/python3" ] && "${SCRIPT_DIR}/.venv/bin/python3" -c "import yaml" 2>/dev/null; then
            PYTHON="${SCRIPT_DIR}/.venv/bin/python3"
        else
            echo "ERROR: PyYAML not found. Run: cd \"${SCRIPT_DIR}\" && python3 -m venv .venv && .venv/bin/pip install 'PyYAML>=6.0'"
            exit 1
        fi
    fi
}

# Usage: deploy_read_config <key>
deploy_read_config() {
    local key="$1"
    "$PYTHON" -c "
import yaml, sys
with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f) or {}
v = cfg.get(sys.argv[2], '')
if v is None:
    v = ''
print(v)
" "$CONFIG" "$key"
}

deploy_load_config() {
    if [ ! -f "$CONFIG" ]; then
        echo "ERROR: Config file not found: $CONFIG"
        echo "Copy deploy.config.example.yaml to deploy.config.yaml and fill in values."
        exit 1
    fi

    GENIFY_APP=$(deploy_read_config genify_app)
    PROFILER_APP=$(deploy_read_config profiler_app)
    POSTGRES_BRANCH=$(deploy_read_config postgres_branch)
    POSTGRES_DATABASE=$(deploy_read_config postgres_database)
    LAKEBASE_INSTANCE_NAME=$(deploy_read_config lakebase_instance_name)
    LAKEBASE_DATABASE_NAME=$(deploy_read_config lakebase_database_name)
    LLM_ENDPOINT=$(deploy_read_config llm_endpoint)
    SUMMARIZER_ENDPOINT=$(deploy_read_config summarizer_endpoint)
    UC_CATALOG=$(deploy_read_config uc_catalog)
    UC_SCHEMA=$(deploy_read_config uc_schema)
    WAREHOUSE_ID=$(deploy_read_config warehouse_id)

    export GENIFY_APP PROFILER_APP POSTGRES_BRANCH POSTGRES_DATABASE
    export LAKEBASE_INSTANCE_NAME LAKEBASE_DATABASE_NAME LLM_ENDPOINT SUMMARIZER_ENDPOINT
    export UC_CATALOG UC_SCHEMA WAREHOUSE_ID

    CLI=(databricks -p "$PROFILE")
}

deploy_preflight() {
    if [ -z "${WAREHOUSE_ID:-}" ]; then
        echo "ERROR: warehouse_id must be set in $CONFIG."
        echo "       Create a SQL warehouse in Databricks, copy its ID, and set warehouse_id."
        echo "       See docs/deploy.md — Before you deploy."
        exit 1
    fi

    if [ -n "${LAKEBASE_INSTANCE_NAME:-}" ] && [ -n "${LAKEBASE_DATABASE_NAME:-}" ]; then
        :
    elif [ -n "${POSTGRES_BRANCH:-}" ] && [ -n "${POSTGRES_DATABASE:-}" ]; then
        :
    else
        echo "ERROR: Genify Lakebase binding: set either"
        echo "         lakebase_instance_name + lakebase_database_name (Provisioned), or"
        echo "         postgres_branch + postgres_database (Autoscaling paths)."
        echo "       See docs/deploy.md."
        exit 1
    fi

    local cmd
    for cmd in databricks npm; do
        command -v "$cmd" &>/dev/null || {
            echo "ERROR: '$cmd' not found."
            exit 1
        }
    done
    command -v "$PYTHON" &>/dev/null || {
        echo "ERROR: Python not found at '$PYTHON'."
        exit 1
    }

    if ! "$PYTHON" -c "from databricks.sdk import WorkspaceClient" 2>/dev/null; then
        echo "ERROR: Python package 'databricks-sdk' is required for Genify app resource updates"
        echo "       (Databricks CLI may reject Lakebase 'postgres' bindings)."
        echo "       Install: pip install 'databricks-sdk>=0.30'  (or add to your .venv)"
        exit 1
    fi

    USER_EMAIL=$("${CLI[@]}" current-user me -o json 2>/dev/null \
        | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['userName'])" 2>/dev/null) || {
        echo "ERROR: Could not authenticate with profile '$PROFILE'."
        exit 1
    }
    export USER_EMAIL
    WORKSPACE_BASE="/Workspace/Users/${USER_EMAIL}/apps"
    export WORKSPACE_BASE

    echo "==> Config: $CONFIG"
    echo "    Profile: $PROFILE"
    echo "    Warehouse: $WAREHOUSE_ID"
    echo "    Genify app: $GENIFY_APP"
    echo "    Profiler app: $PROFILER_APP"
    echo "==> Authenticated as $USER_EMAIL"
}

# Resolve SQL warehouse for UC statements. Uses warehouse_id from config if set, else first RUNNING/STARTING.
deploy_resolve_warehouse() {
    if [ -n "${WAREHOUSE_ID}" ]; then
        WH_ID="${WAREHOUSE_ID}"
        echo "    Using warehouse from config: $WH_ID"
        export WH_ID
        return 0
    fi
    WH_ID=$("${CLI[@]}" sql-warehouses list -o json 2>/dev/null \
        | "$PYTHON" -c "
import sys, json
whs = json.load(sys.stdin).get('warehouses', [])
for w in whs:
    if w.get('state') in ('RUNNING', 'STARTING'):
        print(w['id'])
        break
" 2>/dev/null) || true
    if [ -z "$WH_ID" ]; then
        echo "ERROR: No SQL warehouse available. Start a warehouse or set warehouse_id in $CONFIG."
        exit 1
    fi
    echo "    Using warehouse: $WH_ID"
    export WH_ID
}
