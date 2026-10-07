# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the HookRunner: phase matching, client scoping, order, best-effort."""

from generic_ml_wrapper.application.domain.service.hook import Hook, HookContext, HookPhase
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner


def _context(phase: HookPhase, client: str = "claude", exit_code: int | None = None) -> HookContext:
    return HookContext(
        phase=phase,
        job="JOB-1",
        session_id="JOB-1_001",
        client=client,
        uuid=None,
        resume=False,
        cwd=None,
        exit_code=exit_code,
    )


class _Recording(Hook):
    def __init__(self, log: list[str], label: str) -> None:
        self._log = log
        self._label = label

    def run(self, context: HookContext) -> None:
        self._log.append(self._label)


class _Boom(Hook):
    def run(self, context: HookContext) -> None:
        raise RuntimeError("hook blew up")


def test_runs_only_hooks_bound_to_the_phase_in_order() -> None:
    log: list[str] = []
    runner = HookRunner(
        [
            (HookPhase.PRE_LAUNCH, None, _Recording(log, "pre-a")),
            (HookPhase.POST_SESSION, None, _Recording(log, "post")),
            (HookPhase.PRE_LAUNCH, None, _Recording(log, "pre-b")),
        ]
    )
    runner.run(HookPhase.PRE_LAUNCH, _context(HookPhase.PRE_LAUNCH))
    assert log == ["pre-a", "pre-b"]  # post-session hook did not run; order preserved


def test_client_scope_filters_by_the_run_client() -> None:
    log: list[str] = []
    runner = HookRunner(
        [
            (HookPhase.PRE_LAUNCH, "cursor", _Recording(log, "cursor-only")),
            (HookPhase.PRE_LAUNCH, None, _Recording(log, "every-client")),
            (HookPhase.PRE_LAUNCH, "claude", _Recording(log, "claude-only")),
        ]
    )
    runner.run(HookPhase.PRE_LAUNCH, _context(HookPhase.PRE_LAUNCH, client="claude"))
    assert log == ["every-client", "claude-only"]  # the cursor-scoped hook is skipped


def test_a_failing_hook_is_isolated_and_the_rest_still_run() -> None:
    log: list[str] = []
    runner = HookRunner(
        [
            (HookPhase.POST_SESSION, None, _Boom()),
            (HookPhase.POST_SESSION, None, _Recording(log, "after-boom")),
        ]
    )
    # best-effort: the raising hook must not propagate, and later hooks still run
    runner.run(HookPhase.POST_SESSION, _context(HookPhase.POST_SESSION, exit_code=0))
    assert log == ["after-boom"]


def test_empty_runner_is_a_no_op() -> None:
    HookRunner(()).run(HookPhase.PRE_LAUNCH, _context(HookPhase.PRE_LAUNCH))  # does not raise
