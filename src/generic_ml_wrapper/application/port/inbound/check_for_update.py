# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the rate-limited "a newer gmlw is out" exit-receipt notice."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.update_check import UpdateCheck


class CheckForUpdate(ABC):
    """Report a newer published version: on the receipt once per cache TTL, or when asked."""

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

    @abstractmethod
    def check_now(self) -> UpdateCheck:
        """Check PyPI now, whatever the cache and ``[update] check`` say.

        For when the user asks (``gmlw update``): the answer is wanted, so neither the
        cache nor the receipt's switch stands in the way. A successful check refreshes
        the cache the receipt reads.

        Returns:
            The running and latest versions and how gmlw was installed; the latest is
            ``None`` when PyPI could not be reached.
        """
