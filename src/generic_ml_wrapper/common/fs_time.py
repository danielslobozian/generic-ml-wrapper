# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Best-effort file creation (birth) time, in epoch milliseconds.

Migrating an existing role/environment folder wants a sensible ``created`` date for its
new ``.about.toml``. Birth time is not portable: macOS and Windows expose ``st_birthtime``
directly; many Linux filesystems record a birth time reachable only via ``statx``. This
falls back to the inode-change time when a true birth time is unavailable — good enough
for a best-effort "when did this folder appear" stamp.
"""

from __future__ import annotations

import platform
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def created_ms(path: Path) -> int:
    """Return ``path``'s creation time in epoch milliseconds, best-effort.

    Args:
        path: The file or directory to stamp.

    Returns:
        Epoch milliseconds of the birth time where available, else the inode-change
        time; ``0`` when ``path`` cannot be stat-ed.
    """
    try:
        st = path.stat()
    except OSError:
        return 0
    birth = getattr(st, "st_birthtime", None)  # macOS, Windows, and newer Linux+statx
    if birth is not None:
        return int(birth * 1000)
    if platform.system() == "Linux":
        birth_ms = _linux_statx_birth_ms(path)
        if birth_ms is not None:
            return birth_ms
    return int(st.st_ctime * 1000)  # inode-change time: the closest portable fallback


def _linux_statx_birth_ms(path: Path) -> int | None:
    """The Linux ``statx`` birth time via ``stat --format=%W``, or ``None`` if unavailable."""
    try:
        out = subprocess.check_output(  # noqa: S603  (fixed argv, no shell, trusted path)
            ["stat", "--format=%W", str(path)],  # noqa: S607
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        seconds = int(float(out))
    except ValueError:
        return None
    return seconds * 1000 if seconds > 0 else None
