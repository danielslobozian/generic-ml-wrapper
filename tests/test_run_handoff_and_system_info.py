# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the two adapters that read what the machine and the launch say.

Both used to be direct reaches from inside the command line -- the environment for the
run, the operating system for the account and the platform. They are adapters now, and
these are the tests that could not exist while they were not.
"""

from __future__ import annotations

import getpass
import platform

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap.os_system_info import OsSystemInfoAdapter
from generic_ml_wrapper.adapter.outbound.caller.environment_run_handoff import (
    EnvironmentRunHandoffAdapter,
)


def test_the_launch_announcement_is_read_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """The read side of a seam the caller adapters write when they launch a client."""
    monkeypatch.setenv("GMLW_JOB", "wrapper")
    monkeypatch.setenv("GMLW_SESSION", "wrapper_007")
    monkeypatch.setenv("GMLW_CLIENT", "claude")

    handoff = EnvironmentRunHandoffAdapter().current()

    assert (handoff.job, handoff.session_id, handoff.client) == ("wrapper", "wrapper_007", "claude")


def test_a_client_started_by_hand_belongs_to_no_run(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GMLW_JOB", "GMLW_SESSION", "GMLW_CLIENT"):
        monkeypatch.delenv(name, raising=False)

    handoff = EnvironmentRunHandoffAdapter().current()

    assert (handoff.job, handoff.session_id, handoff.client) == (None, None, None)


def test_the_platform_is_reported_as_the_catalogue_spells_it() -> None:
    assert OsSystemInfoAdapter().platform_name() == platform.system()


def test_the_account_name_is_reported() -> None:
    assert OsSystemInfoAdapter().username() == getpass.getuser()


def test_a_host_that_will_not_name_the_account_is_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Containers with no passwd entry raise rather than guess.

    An empty answer is better than a crash for something used only to address the user.
    """

    def _refuse() -> str:
        raise KeyError("getpwuid(): uid not found")

    monkeypatch.setattr(getpass, "getuser", _refuse)

    assert OsSystemInfoAdapter().username() == ""
