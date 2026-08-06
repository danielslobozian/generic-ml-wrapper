# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the one line ``--version`` prints."""

from __future__ import annotations

from abc import ABC, abstractmethod


class DescribeBuildUseCase(ABC):
    """Render what this build is, for a person reading it in a terminal."""

    @abstractmethod
    def execute(self) -> str:
        """Return the version line.

        Which of the two shapes to use -- a released build named by its stamp, or a
        checkout that was never packaged -- is a decision about what the application is,
        so it is made here rather than by whoever prints it.

        Returns:
            One line, no trailing newline.
        """
