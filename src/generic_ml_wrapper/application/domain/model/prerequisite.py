# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A tool a client's install path needs before the client itself can be installed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prerequisite:
    """A tool a client's install path needs first (e.g. ``uv`` for Vibe).

    Attributes:
        binary: The executable to detect on ``PATH``.
        display: The human-readable name.
        install_unix: The install command on macOS / Linux.
        install_windows: The install command on Windows.
    """

    binary: str
    display: str
    install_unix: str
    install_windows: str

    def install_for(self, system: str) -> str:
        """Return the install command for an OS (``platform.system()`` value)."""
        return self.install_windows if system == "Windows" else self.install_unix
