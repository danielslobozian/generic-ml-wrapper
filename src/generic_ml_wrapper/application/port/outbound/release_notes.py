# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the changelog that ships with gmlw."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ReleaseNotesPort(ABC):
    """Read the running gmlw's changelog."""

    @abstractmethod
    def read(self) -> str | None:
        """Return the changelog's Markdown, or ``None`` when this copy has none; never raises."""
