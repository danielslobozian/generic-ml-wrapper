# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A reference hook that appends a line to a session log at each lifecycle seam."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.hook import HookPhase
from generic_ml_wrapper.application.port.outbound.hook import HookPort
from generic_ml_wrapper.common import paths

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.domain.service.hook import HookContext

_LOG = "sessions.log"


class SessionLogger(HookPort):
    """Append one line to ``~/.gmlw/sessions.log`` at each seam; the simplest hook.

    A reference hook and the simplest example of the lifecycle-hook contract: at
    ``pre-launch`` it records that a session is starting (which client, where), and at
    ``post-session`` that it ended (with the client's exit code). It performs an action —
    a side effect on the world — rather than transforming the run, which is what separates
    a hook from an interceptor. Configure it under ``[[hooks]]`` on the phases you want
    traced; it is a template to copy for your own hooks (a skills deployer, a notifier, a
    cache warmer). Best-effort: any I/O failure is swallowed so the launch is never broken.
    """

    def run(self, context: HookContext) -> None:
        """Append a ``pre-launch`` or ``post-session`` line for this run.

        Args:
            context: The run facts for this seam.
        """
        line = self._line(context)
        try:
            path = self._path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        except OSError:
            # A hook must never break a launch; a log we could not write is not worth it.
            return

    def _path(self) -> Path:
        """The session log location (``~/.gmlw/sessions.log``)."""
        return paths.HOME / _LOG

    @staticmethod
    def _line(context: HookContext) -> str:
        """Render the log line for a seam: an arrow, the session, the client, the outcome."""
        session = f"{context.job}/{context.session_id}"
        where = context.cwd or "."
        if context.phase is HookPhase.PRE_LAUNCH:
            return f"-> start {session} on {context.client} in {where}"
        outcome = "?" if context.exit_code is None else str(context.exit_code)
        return f"<- end   {session} on {context.client} exit {outcome}"
