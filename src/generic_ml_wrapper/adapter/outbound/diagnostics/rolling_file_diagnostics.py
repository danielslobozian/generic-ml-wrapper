# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A rolling-file diagnostics sink — the destination a wrapped session can safely use.

Each record is one line::

    2026-07-24 21:33:20.620 [MainThread:8412] WARNING  upstream failed  client=claude

A caught exception's traceback follows the line it belongs to, indented into the same
record, so the thing that used to be dumped onto the user's screen is preserved in full
where it can actually be read and copied.

Rotation is stdlib :class:`~logging.handlers.RotatingFileHandler`: appended across runs,
rolled at a size cap, a bounded number of backups kept. A diagnostics file that grows
without limit on a long-lived install is a bug of its own, and the stdlib already solved
this correctly.

The whole sink is wrapped in the never-raises contract: an unwritable path, a full disk,
or a permissions change must not take down a session that was otherwise fine.
"""

from __future__ import annotations

import logging
import logging.handlers
import threading
import traceback
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.diagnostics import levels
from generic_ml_wrapper.adapter.outbound.diagnostics.scrub import scrub_record, scrub_text
from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort

#: Roll at 1 MiB, keep 5 backups — ~6 MiB ceiling for the whole facility.
DEFAULT_MAX_BYTES = 1_048_576
DEFAULT_BACKUP_COUNT = 5

_TIMESTAMP = "%Y-%m-%d %H:%M:%S"


class RollingFileDiagnostics(DiagnosticsPort):
    """Write diagnostics as rotating text lines under a log file."""

    def __init__(
        self,
        path: Path,
        level: str | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
    ) -> None:
        """Bind the sink to its file and rotation policy.

        Args:
            path: The log file. Its parent directory is created on demand.
            level: Minimum severity; records below it are dropped.
            max_bytes: Roll the file once it exceeds this size.
            backup_count: How many rolled files to keep.
        """
        self._threshold = levels.threshold(level)
        self._path = path
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        self._lock = threading.Lock()
        self._handler: logging.handlers.RotatingFileHandler | None = None
        self._broken = False

    # ------------------------------------------------------------------
    # DiagnosticsPort
    # ------------------------------------------------------------------

    def debug(self, message: str, **context: object) -> None:
        """Emit a debug-level diagnostic."""
        self._emit(levels.DEBUG, message, None, context)

    def info(self, message: str, **context: object) -> None:
        """Emit an info-level diagnostic."""
        self._emit(levels.INFO, message, None, context)

    def warning(self, message: str, **context: object) -> None:
        """Emit a warning-level diagnostic."""
        self._emit(levels.WARNING, message, None, context)

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        """Emit an error-level diagnostic, rendering *exc*'s traceback when given."""
        self._emit(levels.ERROR, message, exc, context)

    def close(self) -> None:
        """Release the file handle. Idempotent; a later emit reopens in append mode."""
        with self._lock:
            if self._handler is not None:
                self._handler.close()
                self._handler = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(
        self,
        level: str,
        message: str,
        exc: BaseException | None,
        context: dict[str, object],
    ) -> None:
        if levels.ORDER[level] < self._threshold or self._broken:
            return
        try:
            line = _render(level, message, exc, context)
            with self._lock:
                # Hand the rendered line to the handler as a record's whole message. Going
                # through `emit` (rather than writing to the stream) is what gets opening,
                # rotation and flushing from the stdlib instead of from us.
                self._open().emit(
                    logging.LogRecord("gmlw", logging.INFO, __file__, 0, line, None, None)
                )
        except Exception:  # noqa: BLE001 — the never-raises contract
            # One failure is usually permanent (unwritable path, read-only disk), and a
            # sink that retries on every call would turn a broken log into a hot loop.
            self._broken = True

    def _open(self) -> logging.handlers.RotatingFileHandler:
        if self._handler is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                self._path,
                maxBytes=self._max_bytes,
                backupCount=self._backup_count,
                encoding="utf-8",
                delay=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            # `Handler.handleError` prints to stderr when `logging.raiseExceptions` is on
            # — which is exactly the failure this sink exists to prevent, so silence it.
            handler.handleError = _swallow  # type: ignore[method-assign]
            self._handler = handler
        return self._handler


def _swallow(record: logging.LogRecord) -> None:
    """Replace ``Handler.handleError``, whose default prints the failure to stderr."""


def _render(
    level: str,
    message: str,
    exc: BaseException | None,
    context: dict[str, object],
) -> str:
    thread = threading.current_thread()
    stamp = _now()
    fields = scrub_record(context)
    extras = "  ".join(f"{key}={value}" for key, value in fields.items())
    line = (
        f"{stamp} [{thread.name}:{threading.get_ident()}] {level.upper():<7} {scrub_text(message)}"
    )
    if extras:
        line += f"  {extras}"
    if exc is not None:
        rendered = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
        # Indent so a multi-line traceback reads as part of its record rather than as
        # a run of unattributed lines.
        line += "\n" + "\n".join(f"    {row}" for row in scrub_text(rendered).splitlines())
    return line


def _now() -> str:
    from datetime import datetime  # noqa: PLC0415 — kept local; the sink is import-hot

    moment = datetime.now().astimezone()
    return f"{moment.strftime(_TIMESTAMP)}.{moment.microsecond // 1000:03d}"
