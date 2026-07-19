# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for copying a command to the system clipboard (best-effort)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ClipboardPort(ABC):
    """Copy text to the system clipboard when a clipboard tool is available."""

    @abstractmethod
    def copy(self, text: str) -> bool:
        """Copy ``text`` to the clipboard, reporting whether it worked.

        Args:
            text: The text to place on the clipboard.

        Returns:
            ``True`` when the text was copied, ``False`` when no clipboard tool is
            present or the copy failed (never raises — the caller only offers it).
        """
