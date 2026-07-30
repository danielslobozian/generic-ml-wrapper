#!/bin/sh
# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
#
# Install gmlw (generic-ml-wrapper) on Linux or macOS:
#
#   curl -LsSf https://raw.githubusercontent.com/danielslobozian/generic-ml-wrapper/main/install.sh | sh
#
# Ensures uv is present (installing it via Astral's own installer if not), then runs
# `uv tool install generic-ml-wrapper`. No Python prerequisite -- uv fetches its own
# interpreter, so there is nothing to detect or branch on there. Checks the install
# actually landed on PATH and says so loudly rather than exiting silently successful.
set -eu

if ! command -v uv >/dev/null 2>&1; then
  echo "gmlw: uv not found, installing it first..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv's installer updates the shell rc file it detects, not this subshell's PATH.
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    echo "gmlw: uv install did not put 'uv' on PATH." >&2
    echo "See https://docs.astral.sh/uv/getting-started/installation/ and try again." >&2
    exit 1
  fi
fi

echo "gmlw: installing generic-ml-wrapper..."
uv tool install generic-ml-wrapper

bin_dir=$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/bin")
case ":$PATH:" in
  *":$bin_dir:"*)
    ;;
  *)
    echo ""
    echo "-------------------------------------------------------------------"
    echo "gmlw is installed, but $bin_dir is not on your PATH yet."
    echo "Add it, then restart your shell (or open a new terminal):"
    echo ""
    echo "  echo 'export PATH=\"$bin_dir:\$PATH\"' >> ~/.profile"
    echo ""
    echo "(use ~/.bashrc or ~/.zshrc instead of ~/.profile if that's what your"
    echo "shell reads -- check with: echo \$SHELL)"
    echo "-------------------------------------------------------------------"
    ;;
esac

echo ""
echo "gmlw installed. Try:  gmlw --version"
