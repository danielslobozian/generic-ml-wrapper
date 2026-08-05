# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for rendering a status line and recording usage."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ComposeStatuslineUseCase(ABC):
    """Render a client's status line and record its usage."""

    @abstractmethod
    def execute(self, payload_json: str) -> str:
        """Parse the client's payload, record usage, and render the status line.

        Which run this belongs to is not passed in. The status line is invoked by a client
        the wrapper launched, and that launch already announced the job, the session and
        the client to it -- so the run is something to be read, not something a caller
        must know and hand over.

        Args:
            payload_json: The raw JSON the client piped to the status-line command.

        Returns:
            The status line to print (may be empty if the client reported nothing).
        """
