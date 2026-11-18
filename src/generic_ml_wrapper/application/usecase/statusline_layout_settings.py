# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The StatuslineLayoutSettings use case: the ``[statusline]`` layout keys, read and written."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.statusline_layout import (
    AGENT_FIELDS,
    StatuslineLayout,
)
from generic_ml_wrapper.application.port.inbound.statusline_layout_settings import (
    StatuslineLayoutSettings,
)
from generic_ml_wrapper.common import config

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort


class StatuslineLayoutSettingsUseCase(StatuslineLayoutSettings):
    """Read the layout through :mod:`config`, write it through the shared config writer."""

    def __init__(self, writer: ConfigWriterPort, config_file: Callable[[], Path]) -> None:
        """Wire the use case to its writer and the config-file locator.

        Args:
            writer: Persists the layout keys, preserving the rest of the file.
            config_file: Resolves the config file path (indirection for tests).
        """
        self._writer = writer
        self._config_file = config_file

    def load(self) -> StatuslineLayout:
        """Return the configured layout (the full line where nothing is configured)."""
        return StatuslineLayout.of(*config.statusline_layout(self._config_file()))

    def save(self, layout: StatuslineLayout) -> None:
        """Write the three ``[statusline]`` layout keys as lists of block names."""
        agents = [field for field in AGENT_FIELDS if field in layout.agents]
        self._writer.merge(
            self._config_file(),
            [
                ("statusline", "line", list(layout.line)),
                ("statusline", "rows", list(layout.rows)),
                ("statusline", "agents", agents),
            ],
        )
