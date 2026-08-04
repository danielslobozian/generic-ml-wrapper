# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the settings that shape a run before it starts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.companion_settings import CompanionSettings


class RuntimeConfigPort(ABC):
    """Outbound port for what the user configured, as the application needs to know it.

    Distinct from the settable-surface port, which exists so the ``config`` commands can
    render and validate every key. This one answers the handful of questions the
    application itself asks on the way into a run. Where the answers are stored is the
    adapter's business.
    """

    @abstractmethod
    def initialised_version(self) -> str | None:
        """Return the version that ran first-time setup, or ``None`` when it never has."""

    @abstractmethod
    def default_client(self) -> str:
        """Return the client id to wrap when the caller names none."""

    @abstractmethod
    def companion(self) -> CompanionSettings:
        """Return the companion settings; the companion is invisible until a persona is set."""

    @abstractmethod
    def hints_enabled(self) -> bool:
        """Whether one-time tips may be shown."""
