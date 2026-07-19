# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the EditWorkflow use case, driven by fakes."""

import pytest

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.port.inbound.edit_workflow import (
    EditWorkflowCommand,
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.new_workflow import WorkflowNameError
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller, CliCallerProvider
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.edit_workflow import EditWorkflowUseCase


class FakeWorkflows(WorkflowSourcePort):
    def __init__(self, *, existing: bool = True) -> None:
        self.seeded = False
        self.created: str | None = None
        self._existing = existing

    def seed(self) -> None:
        self.seeded = True

    def names(self) -> list[str]:
        return []

    def exists(self, name: str) -> bool:
        return self._existing

    def create(self, name: str) -> str:
        self.created = name  # must never be called when editing
        return f"/workflows/{name}"

    def folder(self, name: str) -> str:
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
) -> EditWorkflowUseCase:
    return EditWorkflowUseCase(
        workflows, store, provider, uuid_factory=lambda: "fixed-uuid", hooks=HookRunner(())
    )


def test_edits_an_existing_workflow_without_creating_it() -> None:
    workflows = FakeWorkflows(existing=True)
    store = FakeStore()
    provider = CapturingProvider()

    exit_code = _use_case(workflows, store, provider).execute(
        EditWorkflowCommand(name="doc-review", client="claude")
    )

    assert exit_code == 0
    assert workflows.seeded is True
    assert workflows.created is None  # editing never creates/overwrites the folder
    assert len(store.recorded) == 1
    assert store.recorded[0].job == "doc-review"
    assert provider.run is not None
    assert provider.run.cwd == "/workflows/doc-review"
    assert provider.run.context == "CONTEXT<authoring:create-workflow>"
    assert "editing" in (provider.run.kickoff or "")
    assert "doc-review" in (provider.run.kickoff or "")


@pytest.mark.parametrize("name", ["Bad Name", "_common", "create-workflow", ""])
def test_rejects_invalid_or_reserved_names(name: str) -> None:
    with pytest.raises(WorkflowNameError):
        _use_case(FakeWorkflows(), FakeStore(), CapturingProvider()).execute(
            EditWorkflowCommand(name=name, client="claude")
        )


def test_refuses_when_the_workflow_does_not_exist() -> None:
    with pytest.raises(WorkflowNotFoundError):
        _use_case(FakeWorkflows(existing=False), FakeStore(), CapturingProvider()).execute(
            EditWorkflowCommand(name="missing", client="claude")
        )
