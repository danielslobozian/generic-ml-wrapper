#!/usr/bin/env bash
# Regenerate the README demo GIFs from the .tape scripts.
#
#   docs/tapes/render.sh
#
# Seeds a throwaway ~/.gmlw ledger + a demo git repo in a temp $HOME (nothing
# touches your real ~/.gmlw), then renders each tape with charmbracelet/vhs.
# No client is launched and no network call is made -- the demos exercise only
# the read/render paths (jobs/sessions/export and the status line).
#
# Requires: vhs, ffmpeg, git, and `gmlw` resolvable (activate the dev env, e.g.
# `uv sync --extra dev` then the project's venv, or set GMLW_BIN=/path/to/gmlw).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

gmlw_bin="${GMLW_BIN:-$(command -v gmlw || true)}"
if [[ -z "$gmlw_bin" ]]; then
  echo "render.sh: no 'gmlw' on PATH. Activate the dev env or set GMLW_BIN." >&2
  exit 1
fi
py="$(dirname "$gmlw_bin")/python"

demo="$(mktemp -d)"
trap 'rm -rf "$demo"' EXIT

# 1. Seed the ledger (job REFACTOR-42 with sessions/turns/costs).
"$py" docs/tapes/seed.py "$demo" >/dev/null

# 2. A clean demo git repo so the status line has a real branch to show.
repo="$demo/acme-api"
git init -q -b feature/checkout-v2 "$repo"
git -C "$repo" config user.email demo@example.com
git -C "$repo" config user.name demo
printf 'print("checkout")\n' > "$repo/app.py"
git -C "$repo" add app.py
git -C "$repo" commit -qm "init"
printf '# work in progress\n' >> "$repo/app.py"   # one dirty file, so dirty:1 shows

# 3. Render, with the demo env + gmlw on PATH visible to the tape's shell.
export HOME="$demo"
export GMLW_DEMO_REPO="$repo"
export PATH="$(dirname "$gmlw_bin"):$PATH"

vhs docs/tapes/usage.tape
vhs docs/tapes/statusline.tape

echo "wrote docs/images/gmlw-usage.gif and docs/images/gmlw-statusline.gif"
