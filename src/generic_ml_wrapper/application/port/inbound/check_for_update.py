# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the rate-limited "a newer gmlw is out" exit-receipt notice."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CheckForUpdate(ABC):
    """Report a newer published version, at most once per cache TTL."""

    @abstractmethod
    def execute(self) -> str | None:
        """Return the latest version, only when it is newer than the running one.

        Reads a small local cache before ever reaching the network, so this is a no-op
        on most launches. Best-effort throughout: off by config, a network failure, or
        a cache-file error all degrade to ``None`` rather than raising.

        Returns:
            The newer version string, or ``None`` when up to date, the check is off,
            or the check could not complete this launch.
        """
