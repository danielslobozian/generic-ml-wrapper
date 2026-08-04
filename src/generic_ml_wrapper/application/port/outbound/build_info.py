# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the stamp a build leaves on the distribution."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BuildInfoPort(ABC):
    """Report the identifier stamped into this distribution when it was built.

    A checkout that was never packaged carries no stamp, and that is an ordinary answer
    rather than a failure: it is how a developer running from source is told apart from a
    user running a release.
    """

    @abstractmethod
    def build_id(self) -> str | None:
        """Return the build identifier, or ``None`` when this is an unbuilt checkout.

        Returns:
            The stamp left at build time, or ``None``.
        """
