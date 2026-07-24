# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Level names and their ordering, shared by every diagnostics sink."""

from __future__ import annotations

DEBUG = "debug"
INFO = "info"
WARNING = "warning"
ERROR = "error"

DEFAULT = WARNING

#: Severity order, mirroring stdlib ``logging`` so a level name means what a reader
#: already expects it to mean.
ORDER: dict[str, int] = {DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40}


def resolve(level: str | None) -> str:
    """Return a known level name, falling back to the default.

    An unknown or empty level is *not* an error: logging configuration must never be
    the thing that stops a run, so a typo in ``[logging] level`` degrades to the
    default rather than raising at startup.

    Args:
        level: A level name, or ``None``.

    Returns:
        One of ``debug`` / ``info`` / ``warning`` / ``error``.
    """
    name = (level or DEFAULT).lower()
    return name if name in ORDER else DEFAULT


def threshold(level: str | None) -> int:
    """Return the numeric severity threshold for *level*."""
    return ORDER[resolve(level)]
