# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem locations the wrapper owns, under ``~/.gmlw`` (or ``$GMLW_HOME``)."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_home() -> Path:
    """Return the folder gmlw keeps everything in: ``$GMLW_HOME``, else ``~/.gmlw``.

    The override moves gmlw's own folder only -- not ``HOME`` -- so a development build
    can keep its own ledger, config and attachments while the clients it launches still
    find their real settings and login under the user's home.
    """
    override = os.environ.get("GMLW_HOME")
    return Path(override).expanduser() if override else Path.home() / ".gmlw"


HOME = resolve_home()
# The single SQLite ledger: jobs, sessions, per-turn metering, session costs.
LEDGER = HOME / "ledger.db"
# Durable per-session provenance: the exact compiled context a session launched with,
# at contexts/<job>/<session>.context.md.
CONTEXTS = HOME / "contexts"
# Opt-in transcript: the per-call in/out/usage trio under transcripts/<job>/<session>/.
TRANSCRIPTS = HOME / "transcripts"
PROFILE = HOME / "profile"
# Place-specific context, one folder per environment (the movie set). The old single
# profile/company folder is migrated into environments/<default_environment>/ on init.
ENVIRONMENTS = HOME / "environments"
# User-editable authoring templates (rule.template.md, later persona.template.md, ...).
# Seeded once and never overwritten, so a user who reshapes a template keeps their version.
# Rules themselves are not stored here: they live per environment and per role.
TEMPLATES = HOME / "templates"
# The personas folder: one persona per file; the selected one is injected as a source.
PERSONAS = HOME / "personas"
# Trusted plugins: one folder per plugin (id = folder name) with a plugin.toml manifest.
# The [callers] override may name a plugin by id instead of a "path.py:Class" spec.
PLUGINS = HOME / "plugins"
# Optional cursor allowance cache ({auto_pct, api_pct}), written by whatever can fetch it
# (cursor doesn't pipe its plan to the status line); merged into the cursor status payload.
CURSOR_PLAN = HOME / "cursor-plan.json"
CREDENTIALS = HOME / "credentials.toml"
# Imported attachments, one read-only folder per version: attachments/<name>/<version>/.
# Their hashes are in the ledger; see docs/ATTACHMENTS.md.
ATTACHMENTS = HOME / "attachments"
# The generic-ml-cache store the context compressor records/replays through.
COMPRESS_CACHE = HOME / "compress-cache"
# Small bits of local UI state (e.g. which one-time exit-receipt hints have been shown).
STATE = HOME / "state"
# User-facing usage report exports, one JSON file per save (exports/<job>-<timestamp>.json),
# written by the TUI's Export → save-to-file destination.
EXPORTS = HOME / "exports"

# The wrapper's own rolling diagnostics. A wrapped session cannot write diagnostics to
# stderr — that is the client's screen — so they land here instead, where they survive
# the session and can actually be read afterwards.
LOGS = HOME / "logs"
LOG_FILE = LOGS / "gmlw.log"
