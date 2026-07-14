# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for detecting which built-in clients are installed."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ClientDetectorPort(ABC):
    """Report which built-in clients are runnable in the current environment."""

    @abstractmethod
    def available(self) -> list[str]:
        """Return the built-in clients found, in canonical order.

        Returns:
            The subset of built-in client names whose command is present (empty
            when none are), ordered canonically (``claude`` first).
        """
