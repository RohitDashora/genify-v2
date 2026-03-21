#!/usr/bin/env bash
# shellcheck shell=bash
# UC function SQL deployment — explicit file order (UC → profiler → genify pipeline runs this first).

deploy_uc_functions() {
    echo ""
    echo "==> Deploying UC functions to ${UC_CATALOG}.${UC_SCHEMA}..."

    deploy_resolve_warehouse
    echo "    UC SQL statements use warehouse: $WH_ID (from warehouse_id in config)"

    export UC_CATALOG UC_SCHEMA WH_ID

    # Explicit order — do not rely on glob ordering.
    local -a UC_SQL_FILES=(
        00_create_schema.sql
        01_get_table_comments.sql
        02_get_table_column_metadata.sql
        03_get_table_profile.sql
        04_get_backward_lineage.sql
        05_get_forward_lineage.sql
        06_get_full_lineage.sql
        07_list_jobs.sql
        08_analyze_table.sql
    )

    local fname sql_file
    for fname in "${UC_SQL_FILES[@]}"; do
        sql_file="${SCRIPT_DIR}/uc_functions/${fname}"
        if [ ! -f "$sql_file" ]; then
            echo "ERROR: Missing UC SQL file: $sql_file"
            exit 1
        fi
        echo "    Deploying $fname..."
        deploy_run_uc_sql_file "$sql_file"
    done
}

# Execute one SQL file via Statement Execution API (Databricks CLI).
deploy_run_uc_sql_file() {
    local sql_file="$1"
    local body
    body=$(
        UC_CATALOG="$UC_CATALOG" UC_SCHEMA="$UC_SCHEMA" WH_ID="$WH_ID" "$PYTHON" -c "
import json, os, sys
path = sys.argv[1]
with open(path) as f:
    sql = f.read()
sql = sql.replace('{{CATALOG}}', os.environ['UC_CATALOG'])
sql = sql.replace('{{SCHEMA}}', os.environ['UC_SCHEMA'])
body = {
    'statement': sql,
    'warehouse_id': os.environ['WH_ID'],
    'wait_timeout': '50s',
}
print(json.dumps(body))
" "$sql_file"
    )
    # Capture stderr separately so JSON on stdout parses cleanly
    local errf rc
    errf=$(mktemp)
    rc=0
    out=$("${CLI[@]}" api post /api/2.0/sql/statements --json "$body" -o json 2>"$errf") || rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "      FAILED: databricks api post (exit $rc)"
        sed 's/^/      /' "$errf"
        rm -f "$errf"
        exit 1
    fi
    rm -f "$errf"
    echo "$out" | "$PYTHON" -c "
import sys, json
raw = sys.stdin.read().strip()
if not raw:
    print('      FAILED: empty response from Statement API')
    sys.exit(1)
try:
    r = json.loads(raw)
    state = r.get('status', {}).get('state', 'UNKNOWN')
    if state == 'SUCCEEDED':
        print('      OK')
    else:
        err = r.get('status', {}).get('error', {}).get('message', '')
        print(f'      FAILED: {state}: {err}')
        sys.exit(1)
except json.JSONDecodeError as e:
    print(f'      FAILED: invalid JSON from CLI: {e}')
    print('      First 200 chars:', repr(raw[:200]))
    sys.exit(1)
"
}
