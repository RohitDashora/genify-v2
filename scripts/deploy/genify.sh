#!/usr/bin/env bash
# shellcheck shell=bash
# Genify app — runs after profiler (includes npm build + staged upload).
# Subshell ensures temp dir cleanup on failure (trap EXIT).

deploy_genify_app() (
    set -euo pipefail

    echo ""
    echo "==> Building Genify frontend..."
    cd "${SCRIPT_DIR}/src/genify/frontend"
    # Prefer npm ci when lockfile is present (reproducible deploys; surfaces lock drift).
    if [ -f package-lock.json ]; then
        npm ci
    else
        npm install
    fi
    npm run build
    cd "${SCRIPT_DIR}"

    GENIFY_SRC="${SCRIPT_DIR}/src/genify"
    if [ ! -f "${GENIFY_SRC}/frontend/dist/index.html" ]; then
        echo "ERROR: ${GENIFY_SRC}/frontend/dist/index.html missing after build."
        exit 1
    fi

    echo ""
    echo "==> Deploying Genify app '${GENIFY_APP}'..."

    STAGING=$(mktemp -d)
    # shellcheck disable=SC2064
    trap 'rm -rf "${STAGING}"' EXIT

    GENIFY_PATH="${WORKSPACE_BASE}/${GENIFY_APP}"
    # Allowlist only runtime artifacts — never upload node_modules, frontend/src, or dev configs.
    mkdir -p "${STAGING}/frontend"
    cp -R "${GENIFY_SRC}/backend" "${STAGING}/"
    cp -R "${GENIFY_SRC}/seed_templates" "${STAGING}/"
    cp "${GENIFY_SRC}/app.yaml" "${STAGING}/"
    cp "${GENIFY_SRC}/requirements.txt" "${STAGING}/"
    cp -R "${GENIFY_SRC}/frontend/dist" "${STAGING}/frontend/"
    find "${STAGING}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find "${STAGING}" -name "*.pyc" -delete 2>/dev/null || true
    find "${STAGING}" -name ".DS_Store" -delete 2>/dev/null || true

    echo "    Staged $(find "${STAGING}" -type f | wc -l | tr -d ' ') files"

    "${CLI[@]}" workspace import-dir "${STAGING}" "${GENIFY_PATH}" \
        --overwrite 2>&1 | tail -3

    if "${CLI[@]}" apps get "${GENIFY_APP}" -o json &>/dev/null; then
        echo "    App exists."
    else
        echo "    Creating app..."
        "${CLI[@]}" apps create "${GENIFY_APP}" \
            --description "AI-powered metadata generator for Unity Catalog & Genie Spaces" \
            --no-compute --no-wait
        sleep 3
    fi

    echo "    Updating resource bindings..."
    # Lakebase postgres bindings: use Python SDK — CLI may reject --json with "unknown field: postgres".
    # sql-warehouse id must match src/genify/app.yaml valueFrom: sql-warehouse
    if ! PROFILE="${PROFILE}" GENIFY_APP="${GENIFY_APP}" WAREHOUSE_ID="${WAREHOUSE_ID}" \
        LLM_ENDPOINT="${LLM_ENDPOINT}" SUMMARIZER_ENDPOINT="${SUMMARIZER_ENDPOINT}" \
        LAKEBASE_INSTANCE_NAME="${LAKEBASE_INSTANCE_NAME:-}" \
        LAKEBASE_DATABASE_NAME="${LAKEBASE_DATABASE_NAME:-}" \
        POSTGRES_BRANCH="${POSTGRES_BRANCH:-}" POSTGRES_DATABASE="${POSTGRES_DATABASE:-}" \
        "$PYTHON" "${SCRIPT_DIR}/scripts/deploy/genify_app_update_resources.py"; then
        echo "ERROR: Genify app resource update failed for ${GENIFY_APP}. Fix config or bind resources in the Apps UI."
        exit 1
    fi

    echo "    Deploying..."
    "${CLI[@]}" apps deploy "${GENIFY_APP}" --source-code-path "${GENIFY_PATH}" --no-wait
    echo "    Genify deployment initiated."
)
