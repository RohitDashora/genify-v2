#!/usr/bin/env bash
# Fail if environment-specific or secret files are tracked by git (public-repo safety).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "check_repo_hygiene: not a git repository" >&2
  exit 1
fi

bad=0
check_not_tracked() {
  local path="$1"
  if git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    echo "ERROR: tracked file must not be in git: $path" >&2
    bad=1
  fi
}

check_not_tracked "deploy.config.yaml"
check_not_tracked "deploy.config.local.yaml"
check_not_tracked ".env"
check_not_tracked ".env.local"
check_not_tracked ".databrickscfg"

if [[ "$bad" -ne 0 ]]; then
  echo "Remove from the index: git rm --cached <file> (then commit)." >&2
  exit 1
fi

echo "check_repo_hygiene: OK (no sensitive paths tracked)."
exit 0
