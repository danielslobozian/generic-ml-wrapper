# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the installed plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.plugin import Plugin


class ListPlugins(ABC):
    """List the plugins installed under the plugins directory."""

    @abstractmethod
    def execute(self) -> list[Plugin]:
        """Return the installed plugins, sorted by id.

        Returns:
            The plugins (empty if none are installed).
        """
