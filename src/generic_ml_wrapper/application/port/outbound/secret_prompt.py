# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for asking a person for a value that must not be echoed."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretPromptPort(ABC):
    """Ask for a secret without it appearing on screen or in the shell's history.

    A port rather than a direct read, for the same reason every other prompt in this
    application is one: what "ask a person" means depends entirely on what is on the other
    end -- a terminal, a pipe, a test -- and none of that is the application's business.
    """

    @abstractmethod
    def ask_secret(self, label: str) -> str:
        """Read one secret value.

        Args:
            label: What is being asked for, shown when there is somebody to show it to.

        Returns:
            The value, with no trailing newline.
        """
