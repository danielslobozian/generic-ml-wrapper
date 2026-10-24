# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Name the running process ``gmlw``, where terminals and process lists look for a name.

Installed as a console script, gmlw runs as ``<interpreter> <script>``, and that full
command line is what a terminal's title bar and ``ps``/``top`` show: on a uv install,
``…/uv/tools/generic-ml-wrapper/bin/python3 …/.local/bin/gmlw``. On Linux and macOS,
renaming the process is enough. A Windows console shows its console title instead, so
there gmlw also titles the console ``gmlw``, and puts the previous title back on exit.

A client gmlw launches stays free to set its own title (claude titles itself with the
session name gmlw hands it); that title wins because it is written later.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from setproctitle import setproctitle

if TYPE_CHECKING:
    from collections.abc import Callable

PROCESS_NAME = "gmlw"
# Longer than any console title Windows keeps (it caps them well below this).
_TITLE_BUFFER_LENGTH = 1024


def name_the_process() -> Callable[[], None]:
    """Rename this process ``gmlw``, and on Windows title the console the same.

    Returns:
        A callable that undoes what must not outlive gmlw: the console title on Windows.
        The process name needs no undoing; it ends with the process.
    """
    setproctitle(PROCESS_NAME)
    return _title_the_console(PROCESS_NAME)


def _title_the_console(title: str) -> Callable[[], None]:
    """Set the Windows console title, returning what restores the previous one.

    Elsewhere, and on Windows without a console (output redirected to a service, say),
    there is nothing to set and the returned callable does nothing.
    """
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415  Windows-only; never loaded elsewhere

        kernel32 = ctypes.WinDLL("kernel32")
        buffer = ctypes.create_unicode_buffer(_TITLE_BUFFER_LENGTH)
        if kernel32.GetConsoleTitleW(buffer, _TITLE_BUFFER_LENGTH):
            previous = buffer.value
            kernel32.SetConsoleTitleW(title)

            def restore() -> None:
                kernel32.SetConsoleTitleW(previous)

            return restore
    return _nothing_to_restore


def _nothing_to_restore() -> None:
    """Restore nothing: there was no console title to change."""
