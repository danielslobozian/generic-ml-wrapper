# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``StatusParsersPort``: which parser understands which client's status payload.

Both clients that host a status line pipe a Claude-Code-compatible payload, so the shared
fields parse the same way and only the allowance block differs. That is why an unknown
client gets Claude's parser rather than a refusal: the fields that matter still read, and a
status line whose job is to always print something must not fail over a name it did not
recognise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.status.claude_status_parser import (
    ClaudeStatusParserAdapter,
)
from generic_ml_wrapper.adapter.outbound.status.cursor_status_parser import (
    CursorStatusParserAdapter,
)
from generic_ml_wrapper.application.port.outbound.status_parsers import StatusParsersPort

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.client_status import (
        ClientStatusParserPort,
    )

_CURSOR = "cursor"


class CataloguedStatusParsersAdapter(StatusParsersPort):
    """Hand out the parser a client's status payload needs."""

    def __init__(self, cursor_plan_cache: Path) -> None:
        """Bind the resolver to what cursor's parser needs beyond the payload.

        Args:
            cursor_plan_cache: Where the cached cursor allowance is kept; cursor does not
                pipe its plan pools to the status line, so its parser folds them in.
        """
        self._cursor_plan_cache = cursor_plan_cache

    def for_client(self, client: str | None) -> ClientStatusParserPort:
        """Return the parser for ``client``, defaulting to Claude's."""
        if client == _CURSOR:
            return CursorStatusParserAdapter(self._cursor_plan_cache)
        return ClaudeStatusParserAdapter()
