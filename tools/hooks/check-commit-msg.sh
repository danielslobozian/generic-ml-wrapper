#!/usr/bin/env bash
# commit-msg guard: reject AI/assistant attribution in the commit message.
# Project policy: commits carry no "Co-Authored-By: <assistant>" trailer and no
# "Generated with <assistant>" line. Enforced here so the rule can't be skipped.
set -euo pipefail

msg_file="$1"

if grep -qiE \
  'co-authored-by:[[:space:]]*.*(claude|copilot|chatgpt|gpt-|anthropic|openai)|generated with[[:space:]]+\[?(claude|copilot|chatgpt)|🤖[[:space:]]*generated' \
  "$msg_file"; then
  echo "✗ Remove AI/assistant attribution from the commit message (project policy)." >&2
  exit 1
fi
