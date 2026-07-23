# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SPIKE: prove the Textual menu is drivable and returns a resume choice (Pilot harness).

The repo has no pytest-asyncio, so each scenario is wrapped in ``asyncio.run`` — Textual's
``run_test``/``Pilot`` is the only async surface and needs nothing more than an event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from textual.pilot import Pilot

from generic_ml_wrapper.adapter.inbound.tui.spike_app import (
    JobChoice,
    MenuChoice,
    SpikeMenuApp,
)

_JOBS = [JobChoice(job="alpha", session_count=3), JobChoice(job="beta", session_count=1)]


def _drive(script: Callable[[Pilot], Awaitable[None]]) -> MenuChoice | None:
    """Run the spike app under Pilot, apply ``script``, return the app's exit value."""

    async def scenario() -> MenuChoice | None:
        app = SpikeMenuApp(_JOBS)
        async with app.run_test() as pilot:
            await script(pilot)
        return app.return_value

    return asyncio.run(scenario())


def test_resume_flow_returns_chosen_job() -> None:
    """Down to 'Resume a job', Enter into the picker, Enter on the first job -> resume alpha."""

    async def script(pilot: Pilot) -> None:
        await pilot.press("down")  # Start -> Resume
        await pilot.press("enter")  # open the job picker
        await pilot.press("enter")  # pick the first job (alpha)

    assert _drive(script) == MenuChoice(action="resume", job="alpha")


def test_quit_returns_none() -> None:
    """The 'q' binding exits with no choice, so the wiring launches nothing."""

    async def script(pilot: Pilot) -> None:
        await pilot.press("q")

    assert _drive(script) is None


def test_escape_from_picker_goes_back_to_menu() -> None:
    """Esc in the picker pops back to the menu (navigation back-and-forth), then quit."""

    async def script(pilot: Pilot) -> None:
        await pilot.press("down")  # -> Resume
        await pilot.press("enter")  # open picker
        await pilot.press("escape")  # back to menu
        await pilot.press("q")  # quit from the menu

    assert _drive(script) is None
