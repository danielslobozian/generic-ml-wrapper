# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for what the user configured, as the delivery layer needs to know it."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.companion_settings import CompanionSettings


class ApplicationSettings(ABC):
    """The questions a delivery adapter asks before and around a run.

    A CLI or a menu has to decide things before any command runs — whether setup is still
    owed, which client to wrap, whether to greet and sign off, whether to offer a tip. All
    four are answers the application owns. A delivery adapter that reads them for itself
    has quietly decided where configuration lives, which is the one thing it must not know.
    """

    @abstractmethod
    def setup_needed(self) -> bool:
        """Whether first-time setup has never run and is owed before anything else."""

    @abstractmethod
    def resolve_client(self, explicit: str | None) -> str:
        """Return the client to wrap: the explicit choice, else the configured default.

        Args:
            explicit: The client named for this invocation, or ``None``.

        Returns:
            The client id to launch.
        """

    @abstractmethod
    def companion(self) -> CompanionSettings:
        """Return the companion settings, for greeting and signing off."""

    @abstractmethod
    def hints_enabled(self) -> bool:
        """Whether one-time tips may be shown."""
