# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for reading a client's installed and latest-published versions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_catalog import ClientInfo


class ClientVersionPort(ABC):
    """Report a client's installed version and its latest published one.

    Every method is best-effort: an offline machine, a slow endpoint, or a client that
    does not answer ``--version`` yields ``None`` rather than an error, so a version
    check never blocks setup or a launch.
    """

    @abstractmethod
    def installed(self, info: ClientInfo) -> str | None:
        """Return the version the local install reports, or ``None`` if undetermined.

        Args:
            info: The catalog entry (its binary and version flag).

        Returns:
            The parsed version string, or ``None`` when the client is absent, times
            out, or prints nothing version-shaped.
        """

    @abstractmethod
    def latest(self, info: ClientInfo) -> str | None:
        """Return the latest published version, or ``None`` if it cannot be fetched.

        Tries the catalog's version probes in order (primary channel, then fallback)
        and returns the first that yields a version.

        Args:
            info: The catalog entry (its ordered version probes).

        Returns:
            The latest version string, or ``None`` when every probe fails.
        """
