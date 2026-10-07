# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ClipboardPort`` backed by whichever native clipboard tool is on ``PATH``."""

from __future__ import annotations

import platform
import shutil
import subprocess

from generic_ml_wrapper.application.port.outbound.clipboard import ClipboardPort

# Per-OS clipboard writers, each reading the text from stdin. The first one found on
# PATH wins; Linux has several depending on X11 / Wayland, so it lists a few.
_CANDIDATES: dict[str, tuple[tuple[str, ...], ...]] = {
    "Darwin": (("pbcopy",),),
    "Windows": (("clip",),),
    "Linux": (
        ("wl-copy",),
        ("xclip", "-selection", "clipboard"),
        ("xsel", "--clipboard", "--input"),
    ),
}


class SystemClipboard(ClipboardPort):
    """Copy via ``pbcopy`` / ``clip`` / ``wl-copy`` / ``xclip`` / ``xsel`` when present."""

    def __init__(self, system: str | None = None) -> None:
        """Bind to an OS name (defaults to the running platform).

        Args:
            system: The ``platform.system()`` value to select a writer for.
        """
        self._system = system or platform.system()

    def copy(self, text: str) -> bool:
        """Pipe ``text`` into the first available clipboard tool; report success.

        Args:
            text: The text to copy.

        Returns:
            ``True`` when a tool accepted the text, ``False`` otherwise.
        """
        for argv in _CANDIDATES.get(self._system, ()):
            if shutil.which(argv[0]) is None:
                continue
            try:
                completed = subprocess.run(  # noqa: S603  (fixed argv, no shell)
                    argv, input=text, text=True, check=False
                )
            except OSError:
                continue
            if completed.returncode == 0:
                return True
        return False
