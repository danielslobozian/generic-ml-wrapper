# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the NewWorkflow use case, driven by fakes."""

import pytest

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import DraftMarker
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflowCommand,
    WorkflowExistsError,
    WorkflowNameError,
    WorkflowOutcome,
)
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller, CliCallerProvider
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.new_workflow import NewWorkflowUseCase

_UNFINISHED = DraftMarker(None, finished=False)


class FakeWorkflows(WorkflowSourcePort):
    def __init__(self, *, existing: bool = False, marker: DraftMarker = _UNFINISHED) -> None:
        self.seeded = False
        self.draft_key: str | None = None
        self.deployed: tuple[str, str] | None = None
        self._existing = existing
        self._marker = marker

    def seed(self) -> None:
        self.seeded = True

    def names(self) -> list[str]:
        return []

    def exists(self, name: str) -> bool:
        return self._existing

    def create(self, name: str) -> str:
        return f"/workflows/{name}"

    def folder(self, name: str) -> str:
        return f"/workflows/{name}"

    def create_draft(self, key: str) -> str:
        self.draft_key = key
        return f"/drafts/{key}"

    def read_draft_marker(self, draft_path: str) -> DraftMarker:
        return self._marker

    def deploy_draft(self, draft_path: str, name: str) -> str:
        self.deployed = (draft_path, name)
        return f"/workflows/{name}"

    def compile(self, mode: CompileMode, name: str | None = None) -> str:
        return f"CONTEXT<{mode.value}:{name}>"


class FakeStore(SessionStorePort):
    def __init__(self) -> None:
        self.recorded: list[Session] = []

    def jobs(self) -> list[str]:
        return []

    def sessions_for_job(self, job: str) -> list[Session]:
        return []

    def record(self, session: Session) -> None:
        self.recorded.append(session)

    def ids_for_job(self, job: str) -> list[str]:
        return []

    def latest_for_job(self, job: str) -> Session | None:
        return None


class CapturingProvider(CliCallerProvider):
    def __init__(self) -> None:
        self.run: RunContext | None = None

    def for_run(self, run: RunContext) -> CliCaller:
        self.run = run
        return _NoopCaller(run)


class _NoopCaller(CliCaller):
    def start_client(self) -> int:
        return 0


def _use_case(
    workflows: FakeWorkflows, store: FakeStore, provider: CapturingProvider
) -> NewWorkflowUseCase:
    return NewWorkflowUseCase(
        workflows, store, provider, uuid_factory=lambda: "fixed-uuid", hooks=HookRunner(())
    )


def test_authoring_runs_in_a_draft_under_the_create_workflow_job() -> None:
    workflows = FakeWorkflows(marker=DraftMarker("nightly-etl", finished=True))
    store = FakeStore()
    provider = CapturingProvider()

    result = _use_case(workflows, store, provider).execute(
        NewWorkflowCommand(name=None, client="claude")
    )

    assert result.exit_code == 0
    assert workflows.seeded is True
    # the session accumulates under create-workflow, not the (unknown) target name
    assert len(store.recorded) == 1
    assert store.recorded[0].job == "create-workflow"
    assert store.recorded[0].session_id == "create-workflow_001"
    assert workflows.draft_key == "create-workflow_001"
    assert provider.run is not None
    assert provider.run.cwd == "/drafts/create-workflow_001"
    assert provider.run.context == "CONTEXT<authoring:create-workflow>"
    assert "draft" in (provider.run.kickoff or "").lower()


def test_deploys_a_finished_named_draft() -> None:
    workflows = FakeWorkflows(marker=DraftMarker("nightly-etl", finished=True))

    result = _use_case(workflows, FakeStore(), CapturingProvider()).execute(
        NewWorkflowCommand(name=None, client="claude")
    )

    assert result.outcome is WorkflowOutcome.DEPLOYED
    assert result.name == "nightly-etl"
    assert workflows.deployed == ("/drafts/create-workflow_001", "nightly-etl")


def test_a_seed_name_seeds_the_kickoff() -> None:
    workflows = FakeWorkflows(marker=DraftMarker("foo", finished=True))
    provider = CapturingProvider()

    _use_case(workflows, FakeStore(), provider).execute(
        NewWorkflowCommand(name="foo", client="claude")
    )

    assert provider.run is not None
    assert "foo" in (provider.run.kickoff or "")


@pytest.mark.parametrize("name", ["Bad Name", "_common", "create-workflow", ""])
def test_rejects_invalid_or_reserved_seed_names(name: str) -> None:
    with pytest.raises(WorkflowNameError):
        _use_case(FakeWorkflows(), FakeStore(), CapturingProvider()).execute(
            NewWorkflowCommand(name=name, client="claude")
        )


def test_a_taken_seed_name_fails_fast() -> None:
    with pytest.raises(WorkflowExistsError):
        _use_case(FakeWorkflows(existing=True), FakeStore(), CapturingProvider()).execute(
            NewWorkflowCommand(name="doc-review", client="claude")
        )


def test_a_taken_name_at_deploy_keeps_the_draft() -> None:
    # No seed name (so no up-front check); the proposed name collides at deploy time.
    workflows = FakeWorkflows(existing=True, marker=DraftMarker("taken", finished=True))

    result = _use_case(workflows, FakeStore(), CapturingProvider()).execute(
        NewWorkflowCommand(name=None, client="claude")
    )

    assert result.outcome is WorkflowOutcome.COLLISION
    assert result.name == "taken"
    assert result.draft_path == "/drafts/create-workflow_001"
    assert workflows.deployed is None  # nothing moved


def test_incomplete_when_the_marker_is_absent_or_unfinished() -> None:
    workflows = FakeWorkflows(marker=DraftMarker("foo", finished=False))

    result = _use_case(workflows, FakeStore(), CapturingProvider()).execute(
        NewWorkflowCommand(name=None, client="claude")
    )

    assert result.outcome is WorkflowOutcome.INCOMPLETE
    assert workflows.deployed is None


def test_a_proposed_unusable_name_is_incomplete() -> None:
    # The session declared it finished but named it something invalid — keep the draft.
    workflows = FakeWorkflows(marker=DraftMarker("Bad Name", finished=True))

    result = _use_case(workflows, FakeStore(), CapturingProvider()).execute(
        NewWorkflowCommand(name=None, client="claude")
    )

    assert result.outcome is WorkflowOutcome.INCOMPLETE
    assert workflows.deployed is None
