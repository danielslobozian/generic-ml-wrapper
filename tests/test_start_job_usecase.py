# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the StartJob use case, driven by fakes for its outbound ports."""

import pytest

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import DraftMarker
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.hook import Hook, HookContext, HookPhase
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJobCommand,
    UnknownWorkflowError,
)
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller, CliCallerProvider
from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.start_job import StartJobUseCase


class FakeStore(SessionStorePort):
    def __init__(self, latest: Session | None = None, ids: list[str] | None = None) -> None:
        self.recorded: list[Session] = []
        self._latest = latest
        self._ids = ids or []

    def jobs(self) -> list[str]:
        return []

    def sessions_for_job(self, job: str) -> list[Session]:
        return []

    def record(self, session: Session) -> None:
        self.recorded.append(session)

    def ids_for_job(self, job: str) -> list[str]:
        return self._ids

    def latest_for_job(self, job: str) -> Session | None:
        return self._latest


class FakeWorkflows(WorkflowSourcePort):
    def __init__(self, *, present: str | None = None, baseline: str = "BASELINE") -> None:
        self.seeded = False
        self._present = present
        self._baseline = baseline
        self.compiled: list[tuple[CompileMode, str | None]] = []

    def seed(self) -> None:
        self.seeded = True

    def names(self) -> list[str]:
        return []

    def exists(self, name: str) -> bool:
        return name == self._present

    def create(self, name: str) -> str:
        raise NotImplementedError

    def folder(self, name: str) -> str:
        return f"/workflows/{name}"

    def create_draft(self, key: str) -> str:
        raise NotImplementedError

    def read_draft_marker(self, draft_path: str) -> DraftMarker:
        raise NotImplementedError

    def deploy_draft(self, draft_path: str, name: str) -> str:
        raise NotImplementedError

    def compile(self, mode: CompileMode, name: str | None = None) -> str:
        self.compiled.append((mode, name))
        if mode is CompileMode.DEFAULT:
            return self._baseline
        return f"CONTEXT<{name}>"


class RecordingCaller(CliCaller):
    def __init__(self, run: RunContext, log: list[str], *, can_resume: bool = True) -> None:
        super().__init__(run)
        self._log = log
        self._can_resume = can_resume

    def can_resume(self) -> bool:
        return self._can_resume

    def start_metering(self) -> None:
        self._log.append("start_metering")

    def start_client(self) -> int:
        self._log.append("start_client")
        return 0

    def end_metering(self) -> None:
        self._log.append("end_metering")


class FakeCredentials(CredentialsStorePort):
    def __init__(self, by_workflow: dict[str, dict[str, str]] | None = None) -> None:
        self._by_workflow = by_workflow or {}

    def resolve(self, workflow: str) -> dict[str, str]:
        return self._by_workflow.get(workflow, {})

    def set(self, workflow: str, name: str, value: str) -> None:
        raise NotImplementedError


class FakeProvider(CliCallerProvider):
    def __init__(self, log: list[str] | None = None, *, can_resume: bool = True) -> None:
        self.log = log if log is not None else []
        self.run: RunContext | None = None
        self._can_resume = can_resume

    def for_run(self, run: RunContext) -> CliCaller:
        self.run = run
        return RecordingCaller(run, self.log, can_resume=self._can_resume)


class RecordingHook(Hook):
    """A hook that appends ``<phase>:<client>:<exit>`` to a shared log when it runs."""

    def __init__(self, log: list[str]) -> None:
        self._log = log

    def run(self, context: HookContext) -> None:
        self._log.append(f"{context.phase.value}:{context.client}:{context.exit_code}")


def _use_case(  # noqa: PLR0913  (mirrors the use case's full port set, plus the greeting)
    store: FakeStore,
    provider: FakeProvider,
    workflows: FakeWorkflows | None = None,
    credentials: FakeCredentials | None = None,
    hooks: HookRunner | None = None,
    greeting: str | None = None,
    capability_card: str | None = None,
) -> StartJobUseCase:
    return StartJobUseCase(
        store=store,
        workflows=workflows or FakeWorkflows(),
        callers=provider,
        uuid_factory=lambda: "fixed-uuid",
        credentials=credentials or FakeCredentials(),
        hooks=hooks or HookRunner(()),
        greeting=lambda: greeting,
        capability_card=lambda: capability_card,
    )


def test_new_session_is_minted_recorded_and_run() -> None:
    store = FakeStore(ids=["JOB-1_001"])
    provider = FakeProvider()
    workflows = FakeWorkflows()
    result = _use_case(store, provider, workflows).execute(
        StartJobCommand(job="JOB-1", client="claude")
    )

    assert result.exit_code == 0
    assert result.job == "JOB-1"
    assert result.session_id == "JOB-1_002"
    assert provider.log == ["start_metering", "start_client", "end_metering"]
    minted = store.recorded[0]
    assert minted.session_id == "JOB-1_002"
    assert provider.run is not None
    assert provider.run.resume is False
    # a plain start now composes the always-on baseline (default mode)
    assert workflows.compiled == [(CompileMode.DEFAULT, None)]
    assert provider.run.context == "BASELINE"


def test_host_greeting_is_prepended_to_a_new_session_context() -> None:
    provider = FakeProvider()
    _use_case(FakeStore(ids=["JOB-1_001"]), provider, greeting="Good evening, Dan.").execute(
        StartJobCommand(job="JOB-1", client="claude")
    )
    assert provider.run is not None
    assert provider.run.context is not None
    assert "# Greeting" in provider.run.context
    assert "Good evening, Dan." in provider.run.context
    assert "BASELINE" in provider.run.context  # ahead of the baseline, not replacing it


def test_greeting_becomes_the_context_when_the_baseline_is_empty() -> None:
    provider = FakeProvider()
    _use_case(
        FakeStore(ids=["JOB-1_001"]),
        provider,
        workflows=FakeWorkflows(baseline=""),
        greeting="Hi, Dan.",
    ).execute(StartJobCommand(job="JOB-1", client="claude"))
    assert provider.run is not None
    assert provider.run.context is not None
    assert "Hi, Dan." in provider.run.context


def test_no_greeting_leaves_the_context_untouched() -> None:
    provider = FakeProvider()
    _use_case(FakeStore(ids=["JOB-1_001"]), provider, greeting=None).execute(
        StartJobCommand(job="JOB-1", client="claude")
    )
    assert provider.run is not None
    assert provider.run.context == "BASELINE"  # companion off → no greeting section


def test_capability_card_is_appended_when_enabled() -> None:
    provider = FakeProvider()
    _use_case(FakeStore(ids=["JOB-1_001"]), provider, capability_card="HOW-TO-CARD").execute(
        StartJobCommand(job="JOB-1", client="claude")
    )
    assert provider.run is not None
    assert provider.run.context is not None
    assert provider.run.context.startswith("BASELINE")  # appended after the baseline
    assert "HOW-TO-CARD" in provider.run.context


def test_capability_card_off_by_default_leaves_context_untouched() -> None:
    provider = FakeProvider()
    _use_case(FakeStore(ids=["JOB-1_001"]), provider, capability_card=None).execute(
        StartJobCommand(job="JOB-1", client="claude")
    )
    assert provider.run is not None
    assert provider.run.context == "BASELINE"


def test_lifecycle_hooks_bracket_the_client_run() -> None:
    shared: list[str] = []  # both hooks and the caller append here, so order is observable
    hooks = HookRunner(
        [
            (HookPhase.PRE_LAUNCH, None, RecordingHook(shared)),
            (HookPhase.POST_SESSION, None, RecordingHook(shared)),
        ]
    )
    provider = FakeProvider(log=shared)
    _use_case(FakeStore(ids=["JOB-1_001"]), provider, hooks=hooks).execute(
        StartJobCommand(job="JOB-1", client="claude")
    )

    # pre-launch runs before metering (exit unknown); post-session runs after teardown
    # (exit code in hand) — the client run is bracketed by the two seams.
    assert shared == [
        "pre-launch:claude:None",
        "start_metering",
        "start_client",
        "end_metering",
        "post-session:claude:0",
    ]


def test_plain_start_with_empty_baseline_injects_no_context() -> None:
    provider = FakeProvider()
    _use_case(FakeStore(ids=["JOB-1_001"]), provider, FakeWorkflows(baseline="")).execute(
        StartJobCommand(job="JOB-1", client="claude")
    )
    assert provider.run is not None
    assert provider.run.context is None  # nothing to inject on a fresh install


def test_resume_latest_reuses_the_recorded_session() -> None:
    latest = Session("JOB-1_003", "JOB-1", "claude", "uuid-3")
    provider = FakeProvider()
    _use_case(FakeStore(latest=latest), provider).execute(
        StartJobCommand(job="JOB-1", client="claude", resume_latest=True)
    )

    assert provider.run is not None
    assert provider.run.resume is True
    assert provider.run.session_id == "JOB-1_003"


def test_resume_latest_falls_back_to_new_when_none_exists() -> None:
    store = FakeStore(latest=None)
    provider = FakeProvider()
    _use_case(store, provider).execute(
        StartJobCommand(job="JOB-1", client="claude", resume_latest=True)
    )

    assert len(store.recorded) == 1
    assert provider.run is not None
    assert provider.run.resume is False


def test_workflow_context_is_compiled_and_injected() -> None:
    store = FakeStore()
    provider = FakeProvider()
    workflows = FakeWorkflows(present="doc-review")

    _use_case(store, provider, workflows).execute(
        StartJobCommand(job="JOB-1", client="claude", workflow="doc-review")
    )

    assert workflows.seeded is True
    assert provider.run is not None
    assert workflows.compiled == [(CompileMode.WORKFLOW, "doc-review")]
    assert provider.run.context == "CONTEXT<doc-review>"
    assert "doc-review" in (provider.run.kickoff or "")


def test_workflow_credentials_are_resolved_into_the_run_env() -> None:
    provider = FakeProvider()
    workflows = FakeWorkflows(present="doc-review")
    credentials = FakeCredentials({"doc-review": {"GITHUB_TOKEN": "ghp_x"}})

    _use_case(FakeStore(), provider, workflows, credentials).execute(
        StartJobCommand(job="JOB-1", client="claude", workflow="doc-review")
    )

    assert provider.run is not None
    assert dict(provider.run.env) == {"GITHUB_TOKEN": "ghp_x"}


def test_no_workflow_means_no_injected_env() -> None:
    provider = FakeProvider()
    _use_case(FakeStore(ids=["JOB-1_001"]), provider).execute(
        StartJobCommand(job="JOB-1", client="claude")
    )
    assert provider.run is not None
    assert provider.run.env == ()


def test_unknown_workflow_is_rejected() -> None:
    workflows = FakeWorkflows(present=None)
    with pytest.raises(UnknownWorkflowError):
        _use_case(FakeStore(), FakeProvider(), workflows).execute(
            StartJobCommand(job="JOB-1", client="claude", workflow="missing")
        )


def test_rejected_start_records_no_ghost_session() -> None:
    store = FakeStore()
    with pytest.raises(UnknownWorkflowError):
        _use_case(store, FakeProvider(), FakeWorkflows(present=None)).execute(
            StartJobCommand(job="JOB-1", client="claude", workflow="missing")
        )
    assert store.recorded == []  # validation happens before the session is persisted


def test_resume_on_client_that_cannot_resume_is_rejected() -> None:
    latest = Session("JOB-1_003", "JOB-1", "codex", "uuid-3")
    provider = FakeProvider(can_resume=False)
    use_case = _use_case(FakeStore(latest=latest), provider)

    with pytest.raises(ResumeNotSupportedError, match="codex"):
        use_case.execute(StartJobCommand(job="JOB-1", client="codex", resume_latest=True))

    assert provider.log == []  # refused before the client was launched


def test_workflow_is_not_injected_when_resuming() -> None:
    latest = Session("JOB-1_003", "JOB-1", "claude", "uuid-3")
    provider = FakeProvider()
    workflows = FakeWorkflows(present="doc-review")

    _use_case(FakeStore(latest=latest), provider, workflows).execute(
        StartJobCommand(job="JOB-1", client="claude", resume_latest=True, workflow="doc-review")
    )

    assert provider.run is not None
    assert provider.run.context is None
