# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Install/restore a client's ``statusLine`` command hook in its JSON settings file.

Both Claude Code (``~/.claude/settings.json``) and cursor-agent
(``~/.cursor/cli-config.json``) point a ``statusLine`` key at ``gmlw statusline``.
This snapshots the prior value on install and puts it back on restore, so the
user's own setting survives a run.

Two safety properties matter because this file is the user's, not ours:
- If the file exists but cannot be parsed as JSON, we NEVER overwrite it (that would
  destroy the user's settings). We raise :class:`SettingsUnreadableError` and the run
  aborts with guidance. "Absent" and "unparseable" are different: absent is fine.
- Writes are atomic (temp file + ``replace``), and restore is ownership-aware: it puts
  the old value back only if this run's value is still installed, so two concurrent
  runs can't clobber each other into leaving ``gmlw statusline`` behind.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log


def statusline_command() -> str:
    """The command a client's ``statusLine`` hook invokes.

    ``gmlw statusline`` when ``gmlw`` is on ``PATH`` (survives reinstalls); otherwise
    the absolute path to the ``gmlw`` beside this interpreter -- so the hook still
    resolves when the client is launched from an environment that lacks ``gmlw`` on
    ``PATH`` (a dev checkout, a venv that isn't activated).
    """
    if shutil.which("gmlw"):
        return "gmlw statusline"
    candidate = Path(sys.executable).with_name("gmlw")
    return f"{candidate} statusline" if candidate.exists() else "gmlw statusline"


class SettingsUnreadableError(Exception):
    """A client settings file exists but is not a readable JSON object.

    Overwriting it would destroy the user's settings, so the run aborts instead.
    """

    def __init__(self, path: Path) -> None:
        """Build the error with actionable guidance for ``path``."""
        self.path = path
        super().__init__(
            f"{path} is not valid JSON.\n\n"
            "The wrapper installs its status line by editing this file, and would have to\n"
            "overwrite it to continue. Overwriting a file it cannot parse would destroy your\n"
            "existing settings (model, permissions, env, hooks), so the run is aborted.\n\n"
            "To fix:\n"
            f"  1. Check it:   python -m json.tool {path}\n"
            "  2. Common causes: // or /* */ comments, or a trailing comma -- JSON allows none.\n"
            f"  3. Or move it aside:  mv {path} {path}.bak   (a fresh one will be created)\n"
            "Then run gmlw again."
        )


@dataclass(frozen=True)
class StatusLineSnapshot:
    """The ``statusLine`` before install, plus what this run installed (for restore)."""

    had_status_line: bool
    previous: object
    installed: object


def install(path: Path, status_line: dict[str, object]) -> StatusLineSnapshot:
    """Install ``status_line`` into the settings at ``path``, returning a snapshot.

    Args:
        path: The client's JSON settings file.
        status_line: The ``statusLine`` value to install.

    Returns:
        A snapshot of the prior ``statusLine`` for :func:`restore`.

    Raises:
        SettingsUnreadableError: If ``path`` exists but is not a JSON object; the file
            is left untouched.
    """
    settings = _load(path)
    installed = dict(status_line)
    snapshot = StatusLineSnapshot("statusLine" in settings, settings.get("statusLine"), installed)
    settings["statusLine"] = installed
    _write(path, settings)
    return snapshot


def install_best_effort(path: Path, status_line: dict[str, object]) -> StatusLineSnapshot | None:
    """Install the status line, or skip it (with a warning) if the file can't be written.

    A :class:`SettingsUnreadableError` still propagates -- the wrapper never overwrites
    settings it cannot parse. An ``OSError`` (an unwritable directory or file) is not
    destructive, so the session simply runs without a status line rather than aborting.

    Args:
        path: The client's JSON settings file.
        status_line: The ``statusLine`` value to install.

    Returns:
        The snapshot for :func:`restore`, or ``None`` when the write failed.
    """
    try:
        return install(path, status_line)
    except OSError as error:
        log.warning(i18n.t("log.statusline_install_failed", path=path, error=error))
        return None


def restore(path: Path, snapshot: StatusLineSnapshot) -> None:
    """Restore the ``statusLine`` captured in ``snapshot`` -- if this run still owns it.

    Best-effort teardown: if the file is no longer readable, or another run has
    installed over this one's value, the file is left as-is (with a warning) rather
    than clobbered.

    Args:
        path: The client's JSON settings file.
        snapshot: The snapshot returned by :func:`install`.
    """
    try:
        settings = _load(path)
    except SettingsUnreadableError:
        log.warning(i18n.t("log.statusline_unreadable", path=path))
        return
    if settings.get("statusLine") != snapshot.installed:
        return  # a later run owns the statusLine now -- don't clobber its value
    if snapshot.had_status_line:
        settings["statusLine"] = snapshot.previous
    else:
        settings.pop("statusLine", None)
    _write(path, settings)


def _load(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SettingsUnreadableError(path) from error
    if not isinstance(raw, dict):
        raise SettingsUnreadableError(path)
    return cast("dict[str, object]", raw)


def _write(path: Path, settings: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Same-directory, per-process temp then atomic replace: a crash mid-write can't
    # truncate the user's file, and a unique name avoids two runs colliding on it.
    temporary = path.parent / f"{path.name}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    temporary.replace(path)
