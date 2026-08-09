# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Picking up an interrupted workflow edit: its folder decides which session that is."""

import pytest
from test_edit_workflow_usecase import (
    CapturingProvider,
    FakeSessionLock,
    FakeStore,
    FakeWorkflows,
    _NoInterrupts,
)

from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnosticsAdapter
from generic_ml_wrapper.application.domain.model.no_edit_to_resume_error import NoEditToResumeError
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.workflow_not_found_error import (
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.resume_edit_workflow_command import (
    ResumeEditWorkflowCommand,
)
from generic_ml_wrapper.application.usecase.hook_runner import HookRunner
from generic_ml_wrapper.application.usecase.launch import LaunchSequence
from generic_ml_wrapper.application.usecase.resume_edit_workflow import ResumeEditWorkflowService

FOLDER = "/workflows/nightly-etl"


def _use_case(
    workflows: FakeWorkflows, store: FakeStore, provider: CapturingProvider
) -> ResumeEditWorkflowService:
    return ResumeEditWorkflowService(
        workflows=workflows,
        store=store,
        callers=provider,
        launch=LaunchSequence(
            HookRunner((), NullDiagnosticsAdapter()),
            NullDiagnosticsAdapter(),
            FakeSessionLock(),
            _NoInterrupts(),
        ),
    )


def _edit(session_id: str, client: str = "claude", cwd: str | None = FOLDER) -> Session:
    return Session(session_id, "gmlw-authoring", client, f"uuid-{session_id}", cwd=cwd)


def test_the_latest_edit_of_this_workflow_is_reopened_in_its_folder() -> None:
    provider = CapturingProvider()
    store = FakeStore(sessions=[_edit("a_001"), _edit("a_002")])

    _use_case(FakeWorkflows(existing=True), store, provider).execute(
        ResumeEditWorkflowCommand(workflow_name="nightly-etl")
    )

    assert provider.run is not None
    assert provider.run.resume is True
    assert provider.run.session_id == "a_002"
    assert provider.run.cwd == FOLDER


def test_the_session_supplies_the_client() -> None:
    provider = CapturingProvider()
    store = FakeStore(sessions=[_edit("a_001", client="cursor")])

    _use_case(FakeWorkflows(existing=True), store, provider).execute(
        ResumeEditWorkflowCommand(workflow_name="nightly-etl")
    )

    assert provider.run is not None
    assert provider.run.client == "cursor"


def test_no_context_is_re_injected() -> None:
    # The client still holds the edit conversation; re-sending would talk over it.
    provider = CapturingProvider()
    store = FakeStore(sessions=[_edit("a_001")])

    _use_case(FakeWorkflows(existing=True), store, provider).execute(
        ResumeEditWorkflowCommand(workflow_name="nightly-etl")
    )

    assert provider.run is not None
    assert provider.run.context is None


def test_sessions_that_ran_elsewhere_do_not_count() -> None:
    # Every edit of every workflow files under one authoring job; only this folder's own.
    provider = CapturingProvider()
    store = FakeStore(sessions=[_edit("a_001", cwd="/wf/something-else")])

    with pytest.raises(NoEditToResumeError):
        _use_case(FakeWorkflows(existing=True), store, provider).execute(
            ResumeEditWorkflowCommand(workflow_name="nightly-etl")
        )


def test_an_edit_recorded_before_folders_were_stored_is_not_resumed() -> None:
    provider = CapturingProvider()
    store = FakeStore(sessions=[_edit("a_001", cwd=None)])

    with pytest.raises(NoEditToResumeError):
        _use_case(FakeWorkflows(existing=True), store, provider).execute(
            ResumeEditWorkflowCommand(workflow_name="nightly-etl")
        )


def test_a_client_that_cannot_reopen_is_refused() -> None:
    provider = CapturingProvider(can_resume=False)
    store = FakeStore(sessions=[_edit("a_001", client="codex")])

    with pytest.raises(NoEditToResumeError) as raised:
        _use_case(FakeWorkflows(existing=True), store, provider).execute(
            ResumeEditWorkflowCommand(workflow_name="nightly-etl")
        )

    assert raised.value.catalogue_key == "error.workflow.no_edit_resume_unsupported"


def test_an_unknown_workflow_is_still_refused_as_unknown() -> None:
    with pytest.raises(WorkflowNotFoundError):
        _use_case(FakeWorkflows(existing=False), FakeStore(), CapturingProvider()).execute(
            ResumeEditWorkflowCommand(workflow_name="nightly-etl")
        )
