#!/usr/bin/env bash
# Pre-commit guard: encode two process rules as a runnable gate.
#   1. Never commit directly to `main`.
#   2. Branch names follow the convention: feature/ tech/ fix/ release/ docs/ chore/ test/
set -euo pipefail

branch="$(git rev-parse --abbrev-ref HEAD)"

# Detached HEAD (rebase, cherry-pick, bisect): not a normal commit — don't gate.
if [ "$branch" = "HEAD" ]; then
  exit 0
fi

if [ "$branch" = "main" ]; then
  echo "✗ Direct commits to 'main' are not allowed — create a branch first." >&2
  exit 1
fi

if ! printf '%s' "$branch" | grep -qE '^(feature|tech|fix|release|docs|chore|test)/'; then
  echo "✗ Branch '$branch' does not follow the naming convention." >&2
  echo "  Use one of: feature/ tech/ fix/ release/ docs/ chore/ test/" >&2
  exit 1
fi
