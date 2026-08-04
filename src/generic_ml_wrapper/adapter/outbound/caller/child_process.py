# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Run the wrapped client as a child process, and hand it a termination it is sent.

A kill or hang-up aimed at gmlw must not kill gmlw where it stands: the relay is still
running and the client's own settings still carry gmlw's status-line hook, both of which
are undone by the teardown that follows a normal return. So the signal is forwarded to
the client instead of ending the wrapper. The client exits, the wait below returns like
any other run, and teardown happens because the call *returned* — not because something
was thrown through the application to make it happen.

The handler is installed here, next to the child it signals, because knowing that a child
exists at all is this adapter's business. Nothing above it needs to know a process was
involved: what leaves this module is an exit code.
"""

from __future__ import annotations

import contextlib
import signal
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence

# Signals that mean "wind up": forwarded to the client so it can exit on its own terms.
# SIGHUP is absent on Windows, where a console close is not delivered this way.
_TERMINATION = (signal.SIGTERM, signal.SIGHUP) if hasattr(signal, "SIGHUP") else (signal.SIGTERM,)

_SIGNAL_EXIT_BASE = 128  # the shell convention: a process killed by signal N exits 128 + N


class ChildProcess:
    """Launches the wrapped client and waits for it, forwarding termination signals."""

    def run(self, argv: Sequence[str], cwd: str | None, env: Mapping[str, str]) -> int:
        """Run ``argv`` to completion and return its exit code.

        Args:
            argv: The resolved command line. Trusted, PATH-resolved, never a shell string.
            cwd: The folder to run in, or ``None`` for the current one.
            env: The full environment for the child.

        Returns:
            The client's exit code; a client killed by a signal reports ``128 + N``, the
            same number a shell would report for it.
        """
        process = subprocess.Popen(argv, cwd=cwd, env=dict(env))  # noqa: S603
        with self._forwarding_termination_to(process):
            return self._exit_code(process.wait())

    @contextlib.contextmanager
    def _forwarding_termination_to(self, process: subprocess.Popen[bytes]) -> Generator[None]:
        """Send termination signals on to *process* for the duration of its run."""

        def forward(signum: int, _frame: object) -> None:
            # Reset first: a second signal ends the wrapper outright, so a client that
            # refuses to exit can never wedge the shutdown.
            signal.signal(signum, signal.SIG_DFL)
            with contextlib.suppress(ProcessLookupError):  # it already exited
                process.send_signal(signum)

        previous = [(sig, signal.signal(sig, forward)) for sig in _TERMINATION]
        try:
            yield
        finally:
            for sig, handler in previous:
                signal.signal(sig, handler)

    def _exit_code(self, returncode: int) -> int:
        """Turn a wait status into a conventional exit code.

        A child killed by a signal reports the negated signal number; every consumer above
        expects the shell's ``128 + N``.
        """
        return _SIGNAL_EXIT_BASE - returncode if returncode < 0 else returncode
