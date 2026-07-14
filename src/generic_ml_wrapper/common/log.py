# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Level-aware, bound-context diagnostic logging to stderr.

A tiny zero-dependency facility for the wrapper's own diagnostics (warnings,
debug traces). It is separate from command output — results and user-facing
errors print to stdout; diagnostics go here, to stderr, gated by a threshold.

Levels mirror stdlib logging: ``debug < info < warning < error``. The threshold
defaults to ``warning`` (quiet), set once at startup from ``[logging] level`` or
the ``GMLW_LOG_LEVEL`` env var. Context (job, session, …) is bound once and
inherited, so deep code need not thread it through.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40}
_DEFAULT = "warning"
_config = {"threshold": _LEVELS[_DEFAULT]}


def configure(level: str | None) -> str:
    """Set the diagnostic threshold; messages below it are dropped.

    Args:
        level: A level name (``debug``/``info``/``warning``/``error``); an unknown
            or empty value falls back to the default.

    Returns:
        The resolved level name.
    """
    name = (level or _DEFAULT).lower()
    if name not in _LEVELS:
        name = _DEFAULT
    _config["threshold"] = _LEVELS[name]
    return name


@dataclass(frozen=True)
class Log:
    """A logger carrying zero or more bound context labels."""

    context: tuple[str, ...] = ()

    def bind(self, *labels: str) -> Log:
        """Return a logger with additional context labels bound.

        Args:
            labels: Context labels to append (empty labels are ignored).

        Returns:
            A new ``Log`` carrying the deeper context.
        """
        return Log(self.context + tuple(label for label in labels if label))

    def debug(self, message: str) -> None:
        """Emit a debug-level message."""
        self._emit("debug", message)

    def info(self, message: str) -> None:
        """Emit an info-level message."""
        self._emit("info", message)

    def warning(self, message: str) -> None:
        """Emit a warning-level message."""
        self._emit("warning", message)

    def error(self, message: str) -> None:
        """Emit an error-level message."""
        self._emit("error", message)

    def _emit(self, level: str, message: str) -> None:
        if _LEVELS[level] < _config["threshold"]:
            return
        parts = ["gmlw", level.upper(), *(f"[{label}]" for label in self.context), message]
        print(" ".join(parts), file=sys.stderr)


log = Log()
"""The default process logger (no bound context)."""
