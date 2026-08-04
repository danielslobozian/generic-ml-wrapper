# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for running the wrapped client: exit codes, and forwarding a termination."""

from __future__ import annotations

import os
import signal
import sys

import pytest

from generic_ml_wrapper.adapter.outbound.caller.child_process import ChildProcess

_SIGTERM_EXIT = 143  # 128 + SIGTERM, the code a shell reports for a terminated process


def test_a_clean_exit_code_passes_through() -> None:
    assert ChildProcess().run([sys.executable, "-c", "raise SystemExit(7)"], None, os.environ) == 7


def test_a_signal_death_becomes_the_shell_convention() -> None:
    assert ChildProcess()._exit_code(-signal.SIGTERM) == _SIGTERM_EXIT
    assert ChildProcess()._exit_code(0) == 0
    assert ChildProcess()._exit_code(2) == 2


def test_the_termination_disposition_is_restored_afterwards() -> None:
    before = signal.getsignal(signal.SIGTERM)
    ChildProcess().run([sys.executable, "-c", ""], None, os.environ)
    assert signal.getsignal(signal.SIGTERM) is before


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal delivery")
def test_a_termination_aimed_at_the_wrapper_reaches_the_client() -> None:
    """The whole point: gmlw is signalled, the client dies, and the run *returns*.

    The wrapper must survive long enough to tear down — stop the relay, put the user's
    status-line settings back. That only happens if the call returns rather than the
    process being killed where it stands.
    """
    # A child that ignores nothing and outlives the test unless it is signalled.
    sleeper = [sys.executable, "-c", "import time; time.sleep(30)"]

    def kill_self_once_started() -> None:
        os.kill(os.getpid(), signal.SIGTERM)

    # Arm a one-shot alarm so the signal arrives while the child is being waited on.
    signal.signal(signal.SIGALRM, lambda *_: kill_self_once_started())
    signal.setitimer(signal.ITIMER_REAL, 0.3)
    try:
        exit_code = ChildProcess().run(sleeper, None, os.environ)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)

    assert exit_code == _SIGTERM_EXIT, "the client was terminated and reported as such"
