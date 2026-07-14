# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for rendering a status line and recording usage."""

from __future__ import annotations

from abc import ABC, abstractmethod


class RenderStatusline(ABC):
    """Render a client's status line and record its usage."""

    @abstractmethod
    def execute(self, payload_json: str, job: str | None, session: str | None) -> str:
        """Parse the client's payload, record usage, and render the status line.

        Args:
            payload_json: The raw JSON the client piped to the status-line command.
            job: The active job, or ``None`` if unknown (usage is not recorded then).
            session: The active session, or ``None`` if unknown.

        Returns:
            The status line to print (may be empty if the client reported nothing).
        """
