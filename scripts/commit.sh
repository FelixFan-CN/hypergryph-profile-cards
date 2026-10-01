#!/usr/bin/env bash
# 提交渲染产物。仅在 action.yml 判定 changed == true 时才会被调用。
set -euo pipefail

cd "${GITHUB_WORKSPACE:-.}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

PATHS="${PC_COMMIT_PATHS:-}"
if [ -z "$PATHS" ]; then
  if [ -n "${PC_OUTPUT_DIR:-}" ]; then
    PATHS="$PC_OUTPUT_DIR"
  else
    PATHS="${PC_ASSETS_DIR:-assets}"
  fi
fi

# shellcheck disable=SC2086
git add $PATHS

if git diff --cached --quiet; then
  echo "产物无变化，跳过提交"
  exit 0
fi

git commit -m "${PC_COMMIT_MESSAGE:-chore: update profile cards}"
git push