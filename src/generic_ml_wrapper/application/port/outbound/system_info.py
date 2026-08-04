# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the facts the machine knows about itself."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SystemInfoPort(ABC):
    """Report what the operating system says about the account and the platform.

    Two questions, one seam: both are answers the machine gives about itself, neither is
    anything the application can work out, and an implementation for a different host --
    a container, a test -- answers both or neither.
    """

    @abstractmethod
    def username(self) -> str:
        """Return the name of the account this is running under.

        Returns:
            The account name; an empty string when the host will not say.
        """

    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform's name, as the client catalogue spells it.

        Returns:
            ``"Linux"``, ``"Darwin"``, ``"Windows"``, or an empty string when unknown.
        """
