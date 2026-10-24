# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the session files the clients themselves write."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.session_analysis import SessionRecord


class SessionFilesPort(ABC):
    """Find a client's own session file, and read its metadata.

    Only metadata is read: types, timestamps, token counts, tool names. What the user,
    the model or a tool wrote is never read as text.
    """

    @abstractmethod
    def analyzable_clients(self) -> frozenset[str]:
        """The clients whose session files can be read (``claude``, ``codex``)."""

    @abstractmethod
    def locate(self, client: str, uuid: str) -> str | None:
        """The file in which ``client`` keeps its session ``uuid``, or ``None`` if gone.

        Args:
            client: The client that ran the session.
            uuid: The client's own id for the session.
        """

    @abstractmethod
    def read(self, source: str) -> SessionRecord | None:
        """Read the session file at ``source``, telling the client from the file itself.

        Args:
            source: The file's path.

        Returns:
            The session's record, or ``None`` when the file is missing, unreadable, or
            not a session file of an analysable client.
        """
