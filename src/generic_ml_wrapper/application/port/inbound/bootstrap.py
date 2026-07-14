# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for first-run self-initialization."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Bootstrap(ABC):
    """Ensure the wrapper's runtime layout exists, creating only what is missing."""

    @abstractmethod
    def execute(self) -> None:
        """Create any missing parts of the ``~/.gmlw`` layout (idempotent)."""
