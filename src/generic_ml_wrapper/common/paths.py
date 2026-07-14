# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem locations the wrapper owns, under ``~/.gmlw``."""

from __future__ import annotations

from pathlib import Path

HOME = Path.home() / ".gmlw"
# The single SQLite ledger: jobs, sessions, per-turn metering, session costs.
LEDGER = HOME / "ledger.db"
# Durable per-session provenance: the exact compiled context a session launched with,
# at contexts/<job>/<session>.context.md.
CONTEXTS = HOME / "contexts"
# Opt-in transcript: the per-call in/out/usage trio under transcripts/<job>/<session>/.
TRANSCRIPTS = HOME / "transcripts"
WORKFLOWS = HOME / "workflows"
PROFILE = HOME / "profile"
RULES = HOME / "rules"
CREDENTIALS = HOME / "credentials.toml"
# Authoring sessions (gmlw workflow new) live apart from real work jobs, so they
# never appear in `gmlw jobs` and their spend is its own bucket.
AUTHORING = HOME / "authoring"
# The generic-ml-cache store the context compressor records/replays through.
COMPRESS_CACHE = HOME / "compress-cache"
