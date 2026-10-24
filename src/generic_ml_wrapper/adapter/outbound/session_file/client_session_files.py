# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``SessionFilesPort``: Claude Code's and Codex's own session files."""

from __future__ import annotations

import os
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.caller import codex_session_index
from generic_ml_wrapper.adapter.outbound.session_file import (
    claude_session_file,
    codex_session_file,
)
from generic_ml_wrapper.adapter.outbound.session_file.jsonl import records
from generic_ml_wrapper.application.domain.model.session_analysis import SessionRecord
from generic_ml_wrapper.application.port.outbound.session_files import SessionFilesPort

# How many of a file's first records are looked at to tell whose it is: Claude opens with
# bookkeeping records that carry no session id.
_SNIFF = 20


def claude_home() -> Path:
    """Claude Code's config folder: ``$CLAUDE_CONFIG_DIR`` when set, else ``~/.claude``."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".claude"


class ClientSessionFiles(SessionFilesPort):
    """Find and read the session files Claude Code and Codex keep in their own folders."""

    def analyzable_clients(self) -> frozenset[str]:
        """Claude Code and Codex, the clients whose files record usage and tool calls."""
        return frozenset({claude_session_file.CLIENT, codex_session_file.CLIENT})

    def locate(self, client: str, uuid: str) -> str | None:
        """The file ``client`` keeps session ``uuid`` in, or ``None``."""
        if client == codex_session_file.CLIENT:
            found = codex_session_index.rollout(uuid)
        elif client == claude_session_file.CLIENT:
            found = next((claude_home() / "projects").glob(f"*/{uuid}.jsonl"), None)
        else:
            found = None
        return None if found is None else str(found)

    def read(self, source: str) -> SessionRecord | None:
        """Read ``source`` with the reader of the client that wrote it, if any."""
        path = Path(source).expanduser()
        try:
            client = _client_of(path)
            if client == codex_session_file.CLIENT:
                return codex_session_file.read(path)
            if client == claude_session_file.CLIENT:
                return claude_session_file.read(path)
        except OSError:
            return None
        return None


def _client_of(path: Path) -> str | None:
    """Which client wrote the file at ``path``, judged from its first records.

    A Codex rollout opens with its ``session_meta``; a Claude Code file's conversation
    records carry a ``sessionId``.
    """
    if not path.is_file():
        return None
    for position, record in enumerate(records(path)):
        if position == 0 and record.get("type") == codex_session_file.SESSION_META:
            return codex_session_file.CLIENT
        if "sessionId" in record:
            return claude_session_file.CLIENT
        if position >= _SNIFF:
            break
    return None
