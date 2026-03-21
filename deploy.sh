#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Genify deploy — UC functions → Profiler app → Genify app (npm build + deploy)
# Usage: ./deploy.sh --profile <name> [--config path]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<'USAGE'
Usage: ./deploy.sh --profile <databricks-cli-profile> [--config <path>]

  Order: UC SQL functions → MCP Profiler app → Genify app (includes npm run build).

  --profile, -p   Required. Databricks CLI profile (~/.databrickscfg).
  --config, -c    Config YAML (default: ./deploy.config.yaml next to this script).

  Prerequisites: databricks CLI, npm, Python 3 + PyYAML (or repo .venv with PyYAML).
  deploy.config.yaml must include warehouse_id (see docs/deploy.md).
USAGE
}

PROFILE=""
CONFIG="${SCRIPT_DIR}/deploy.config.yaml"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile | -p)
            PROFILE="${2:-}"
            shift 2
            ;;
        --config | -c)
            CONFIG="${2:-}"
            shift 2
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [[ -z "$PROFILE" ]]; then
    echo "ERROR: --profile is required."
    usage
    exit 1
fi

export SCRIPT_DIR PROFILE CONFIG

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/scripts/deploy/common.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/scripts/deploy/uc_functions.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/scripts/deploy/profiler.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/scripts/deploy/genify.sh"

deploy_resolve_python
deploy_load_config
deploy_preflight

deploy_uc_functions
deploy_profiler_app
deploy_genify_app

echo ""
echo "==> Deployment complete!"

GENIFY_URL=$("${CLI[@]}" apps get "$GENIFY_APP" -o json 2>/dev/null \
    | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('url',''))" 2>/dev/null || true)
PROFILER_URL=$("${CLI[@]}" apps get "$PROFILER_APP" -o json 2>/dev/null \
    | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('url',''))" 2>/dev/null || true)

echo ""
echo "    Genify:   ${GENIFY_URL:-<deploying>}"
echo "    Profiler: ${PROFILER_URL:-<deploying>}"
echo ""
echo "    Note: Apps may take 1-2 minutes to start after deployment."
echo "    Check logs: <app-url>/logz"
