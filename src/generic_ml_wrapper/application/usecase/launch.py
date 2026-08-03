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

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.run import RunContext
    from generic_ml_wrapper.application.domain.service.diagnostics import Diagnostics
    from generic_ml_wrapper.application.domain.service.localizer import Localizer
    from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller
    from generic_ml_wrapper.application.usecase.hook_runner import HookRunner


class LaunchSequence:
    """The bracketed run: pre-launch hooks, metering, the client, teardown, post-session."""

    def __init__(self, hooks: HookRunner, diagnostics: Diagnostics, localizer: Localizer) -> None:
        """Bind the sequence to its hooks and the collaborators that report a bad teardown.

        Args:
            hooks: The lifecycle hook runner (a no-op when nothing is configured).
            diagnostics: Where a failed metering teardown is reported.
            localizer: Renders that report in the language the wrapper is speaking.
        """
        self._hooks = hooks
        self._diagnostics = diagnostics
        self._localizer = localizer

    def run(self, caller: CliCaller, run: RunContext) -> int:
        """Run the client through its lifecycle: pre-launch hooks, metering, post-session hooks.

        ``pre-launch`` hooks run after the caller is resolved and before metering starts, so
        they can prepare the environment the client is about to launch into. The client then
        runs (blocking). Whatever happens — a clean exit or a launch that raised — metering is
        torn down and the ``post-session`` hooks run in a ``finally``, carrying the exit code
        when there is one. Teardown and hooks are best-effort and never mask the run's outcome.

        Args:
            caller: The caller resolved for this run.
            run: The run being launched (the source of the hooks' facts).

        Returns:
            The client's exit code.
        """
        self._hooks.run(
            HookPhase.PRE_LAUNCH, self._context(run, HookPhase.PRE_LAUNCH, exit_code=None)
        )
        caller.start_metering()
        exit_code: int | None = None
        try:
            exit_code = caller.start_client()
            return exit_code  # noqa: RET504  captured so the finally's post-session hook has it
        finally:
            try:
                caller.end_metering()
            except Exception as error:  # noqa: BLE001  teardown must never crash the run
                self._diagnostics.warning(
                    self._localizer.t("log.metering_teardown_failed", error=error),
                    key="log.metering_teardown_failed",
                )
            self._hooks.run(
                HookPhase.POST_SESSION, self._context(run, HookPhase.POST_SESSION, exit_code)
            )

    def _context(self, run: RunContext, phase: HookPhase, exit_code: int | None) -> HookContext:
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
