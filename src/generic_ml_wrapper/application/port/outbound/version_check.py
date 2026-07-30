# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for checking a package's latest published version."""

from __future__ import annotations

from abc import ABC, abstractmethod


class VersionCheckPort(ABC):
    """Report the latest version a package has published."""

    @abstractmethod
    def latest_version(self, package: str) -> str | None:
        """Return ``package``'s latest published version.

        Args:
            package: The package name (its distribution name, e.g. ``"generic-ml-wrapper"``).

        Returns:
            The latest version string, or ``None`` on any failure (network, timeout,
            an unreadable or unexpected response) — never raises.
        """
