# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The filesystem locations the wrapper owns, derived from one root.

Every location is a function of ``home``, so a caller handed a different root gets a
consistent tree — which is what makes the layout testable without patching module state.
The composition root builds one and hands out the branches each adapter needs; the
process-wide default below exists only for the call sites that still reach for it
directly, and goes away when the root becomes an injected dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def _default_home() -> Path:
    return Path.home() / ".gmlw"


@dataclass
class Paths:
    """The ``~/.gmlw`` tree: every file and folder the wrapper reads or writes.

    Every location is derived from :attr:`home`, so pointing the root elsewhere moves the
    whole tree with it — which is how a test isolates itself from the real one.
    """

    home: Path = field(default_factory=_default_home)

    @property
    def ledger(self) -> Path:
        """The single SQLite ledger: jobs, sessions, per-turn metering, session costs."""
        return self.home / "ledger.db"

    @property
    def contexts(self) -> Path:
        """Durable per-session provenance: the exact compiled context a session launched with."""
        return self.home / "contexts"

    @property
    def transcripts(self) -> Path:
        """Opt-in transcript: the per-call in/out/usage trio under ``<job>/<session>/``."""
        return self.home / "transcripts"

    @property
    def workflows(self) -> Path:
        """The runnable workflows, one folder each."""
        return self.home / "workflows"

    @property
    def profile(self) -> Path:
        """The user's own profile: roles and the notebook that follows them between tools."""
        return self.home / "profile"

    @property
    def environments(self) -> Path:
        """Place-specific context, one folder per environment (the movie set)."""
        return self.home / "environments"

    @property
    def templates(self) -> Path:
        """User-editable authoring templates, seeded once and never overwritten.

        Rules themselves are not stored here: they live per environment and per role.
        """
        return self.home / "templates"

    @property
    def personas(self) -> Path:
        """One persona per file; the selected one is injected as a context source."""
        return self.home / "personas"

    @property
    def plugins(self) -> Path:
        """Trusted plugins, one folder per plugin (id = folder name) with a manifest."""
        return self.home / "plugins"

    @property
    def cursor_plan(self) -> Path:
        """Optional cursor allowance cache, merged into the cursor status payload."""
        return self.home / "cursor-plan.json"

    @property
    def credentials(self) -> Path:
        """The credentials a workflow resolves its environment from."""
        return self.home / "credentials.toml"

    @property
    def authoring(self) -> Path:
        """Authoring sessions, kept apart from real work jobs so their spend is its own bucket."""
        return self.home / "authoring"

    @property
    def drafts(self) -> Path:
        """In-progress workflow drafts, one folder per authoring session.

        A sibling of ``workflows`` rather than a folder inside it: a draft is moved into
        place atomically when it is finished, so a half-authored workflow never lists as
        runnable.
        """
        return self.home / "drafts"

    @property
    def compress_cache(self) -> Path:
        """The generic-ml-cache store the context compressor records and replays through."""
        return self.home / "compress-cache"

    @property
    def state(self) -> Path:
        """Small bits of local UI state (e.g. which one-time hints have been shown)."""
        return self.home / "state"

    @property
    def exports(self) -> Path:
        """User-facing usage report exports, one JSON file per save."""
        return self.home / "exports"

    @property
    def workflow_backups(self) -> Path:
        """Workflows displaced by an import.

        Deliberately a sibling of ``workflows`` rather than a folder inside it: anything
        under ``workflows`` with a ``workflow.md`` lists as runnable, so keeping backups
        out makes "a backup is never a workflow" structural instead of a filter that has
        to be remembered.
        """
        return self.home / "workflow-backups"

    @property
    def logs(self) -> Path:
        """The wrapper's own rolling diagnostics.

        A wrapped session cannot write diagnostics to stderr — that is the client's
        screen — so they land here instead, where they survive the session.
        """
        return self.home / "logs"

    @property
    def log_file(self) -> Path:
        """The rolling diagnostics file itself."""
        return self.logs / "gmlw.log"

    @property
    def config_file(self) -> Path:
        """The optional ``config.toml``."""
        return self.home / "config.toml"


paths = Paths()
"""The process-wide default tree, rooted at ``~/.gmlw``."""
