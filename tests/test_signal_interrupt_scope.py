# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for handing the interrupt to the client while it holds the terminal.

Moved here from the command line's own tests, where the same behaviour used to live as a
private helper. It is an adapter now, so it is tested as one: the assertions did not have
to change, only what they are pointed at.
"""

from __future__ import annotations

import signal

import pytest

from generic_ml_wrapper.adapter.outbound.caller.signal_interrupt_scope import SignalInterruptScope


def test_the_interrupt_is_absorbed_inside_the_scope() -> None:
    before = signal.getsignal(signal.SIGINT)

    with SignalInterruptScope().client_owns_interrupts():
        installed = signal.getsignal(signal.SIGINT)
        assert installed is not before
        assert callable(installed)
        assert installed(signal.SIGINT, None) is None  # absorbed, not raised

    assert signal.getsignal(signal.SIGINT) is before


def test_only_the_interrupt_is_taken() -> None:
    """A kill is not handled here.

    The caller adapter forwards a termination to the client it launched, so the run ends
    by returning through the launch sequence -- which is what lets teardown happen. Taking
    it here would unwind straight past that.
    """
    before_term = signal.getsignal(signal.SIGTERM)

    with SignalInterruptScope().client_owns_interrupts():
        assert signal.getsignal(signal.SIGTERM) is before_term

    assert signal.getsignal(signal.SIGTERM) is before_term


def test_the_previous_handler_is_restored_even_when_the_block_raises() -> None:
    before = signal.getsignal(signal.SIGINT)
    message = "the client died"

    with (
        pytest.raises(RuntimeError, match=message),
        SignalInterruptScope().client_owns_interrupts(),
    ):
        raise RuntimeError(message)

    assert signal.getsignal(signal.SIGINT) is before
