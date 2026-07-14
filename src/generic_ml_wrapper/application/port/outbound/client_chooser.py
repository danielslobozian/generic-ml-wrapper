# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for asking which client to default to on first run."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ClientChooserPort(ABC):
    """Ask which of several installed clients should become the default."""

    @abstractmethod
    def choose(self, candidates: list[str]) -> str | None:
        """Pick one client from the candidates.

        Args:
            candidates: The installed clients to choose among (two or more).

        Returns:
            The chosen client, or ``None`` when no choice can be made (for
            example, a non-interactive invocation that must not block).
        """
