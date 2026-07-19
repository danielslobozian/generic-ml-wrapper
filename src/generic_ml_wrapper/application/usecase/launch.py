# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Run a resolved caller with its lifecycle hooks — the shared launch sequence.

Both ``StartJob`` and ``NewWorkflow`` end the same way: a caller is resolved for the run,
metering is set up, the client runs (blocking) until it exits, and metering is torn down.
This centralises that sequence and brackets it with the two lifecycle hook seams —
``pre-launch`` before the client starts and ``post-session`` after it exits — so the
ordering, the exit-code capture, and the never-break-the-run guarantees live in one place.

It sits in the application ring, not the domain: it drives the ``CliCaller`` outbound port,
which the domain may not import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.hook import HookContext, HookPhase
from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.run import RunContext
    from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
    from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller


def run_with_hooks(caller: CliCaller, run: RunContext, hooks: HookRunner) -> int:
    """Run the client through its lifecycle: pre-launch hooks, metering, post-session hooks.

    ``pre-launch`` hooks run after the caller is resolved and before metering starts, so
    they can prepare the environment the client is about to launch into. The client then
    runs (blocking). Whatever happens — a clean exit or a launch that raised — metering is
    torn down and the ``post-session`` hooks run in a ``finally``, carrying the exit code
    when there is one. Teardown and hooks are best-effort and never mask the run's outcome.

    Args:
        caller: The caller resolved for this run.
        run: The run being launched (the source of the hooks' facts).
        hooks: The lifecycle hook runner (a no-op when nothing is configured).

    Returns:
        The client's exit code.
    """
    hooks.run(HookPhase.PRE_LAUNCH, _context(run, HookPhase.PRE_LAUNCH, exit_code=None))
    caller.start_metering()
    exit_code: int | None = None
    try:
        exit_code = caller.start_client()
        return exit_code  # noqa: RET504  captured so the finally's post-session hook has it
    finally:
        try:
            caller.end_metering()
        except Exception as error:  # noqa: BLE001  teardown must never crash the run
            log.warning(i18n.t("log.metering_teardown_failed", error=error))
        hooks.run(HookPhase.POST_SESSION, _context(run, HookPhase.POST_SESSION, exit_code))


def _context(run: RunContext, phase: HookPhase, exit_code: int | None) -> HookContext:
    """Project the run onto the minimal, hook-facing :class:`HookContext` for a phase."""
    return HookContext(
        phase=phase,
        job=run.job,
        session_id=run.session_id,
        client=run.client,
        uuid=run.uuid,
        resume=run.resume,
        cwd=run.cwd,
        exit_code=exit_code,
    )
