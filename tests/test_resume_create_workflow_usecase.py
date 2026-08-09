# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Carrying on an unfinished create-workflow interview."""

import pytest
from test_create_workflow_usecase import (
    CapturingProvider,
    FakeSessionLock,
    FakeStore,
    FakeWorkflows,
    _authoring_session,
    _draft,
    _NoInterrupts,
)

from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnosticsAdapter
from generic_ml_wrapper.application.domain.model.no_such_draft_error import NoSuchDraftError
from generic_ml_wrapper.application.port.inbound.resume_create_workflow_command import (
    ResumeCreateWorkflowCommand,
)
from generic_ml_wrapper.application.usecase.hook_runner import HookRunner
from generic_ml_wrapper.application.usecase.launch import LaunchSequence
from generic_ml_wrapper.application.usecase.resume_create_workflow import (
    ResumeCreateWorkflowService,
)


def _use_case(
    workflows: FakeWorkflows, store: FakeStore, provider: CapturingProvider
) -> ResumeCreateWorkflowService:
    return ResumeCreateWorkflowService(
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


def test_the_latest_unfinished_draft_is_reopened_in_its_own_folder() -> None:
    provider = CapturingProvider()
    workflows = FakeWorkflows(drafts=[_draft("d_001")])
    store = FakeStore(sessions=[_authoring_session("d_001")])

    _use_case(workflows, store, provider).execute(ResumeCreateWorkflowCommand())

    assert provider.run is not None
    assert provider.run.resume is True
    assert provider.run.cwd == "/drafts/d_001"
    assert workflows.seeded is True


def test_the_session_supplies_the_client_not_the_configured_default() -> None:
    provider = CapturingProvider()
    workflows = FakeWorkflows(drafts=[_draft("d_001")])
    store = FakeStore(sessions=[_authoring_session("d_001", client="cursor")])

    _use_case(workflows, store, provider).execute(ResumeCreateWorkflowCommand())

    assert provider.run is not None
    assert provider.run.client == "cursor"


def test_no_authoring_context_is_re_injected() -> None:
    # The client already holds the interview; re-sending it would talk over that history.
    provider = CapturingProvider()
    workflows = FakeWorkflows(drafts=[_draft("d_001")])
    store = FakeStore(sessions=[_authoring_session("d_001")])

    _use_case(workflows, store, provider).execute(ResumeCreateWorkflowCommand())

    assert provider.run is not None
    assert provider.run.context is None


def test_a_named_draft_is_picked_over_the_latest() -> None:
    provider = CapturingProvider()
    workflows = FakeWorkflows(drafts=[_draft("d_001"), _draft("d_002")])
    store = FakeStore(sessions=[_authoring_session("d_001"), _authoring_session("d_002")])

    _use_case(workflows, store, provider).execute(ResumeCreateWorkflowCommand(draft_key="d_002"))

    assert provider.run is not None
    assert provider.run.session_id == "d_002"


def test_picking_the_latest_skips_a_finished_draft() -> None:
    # A finished draft is not waiting on the user — it converged and was blocked from
    # deploying, and reopening it silently would hide that.
    provider = CapturingProvider()
    workflows = FakeWorkflows(drafts=[_draft("d_001", finished=True)])

    with pytest.raises(NoSuchDraftError) as raised:
        _use_case(workflows, FakeStore(), provider).execute(ResumeCreateWorkflowCommand())

    assert raised.value.catalogue_key == "error.draft.none_unfinished"


def test_an_unknown_draft_is_refused() -> None:
    with pytest.raises(NoSuchDraftError) as raised:
        _use_case(FakeWorkflows(drafts=[]), FakeStore(), CapturingProvider()).execute(
            ResumeCreateWorkflowCommand(draft_key="d_404")
        )

    assert raised.value.catalogue_key == "error.draft.not_found"


def test_a_draft_whose_session_was_never_recorded_is_refused() -> None:
    workflows = FakeWorkflows(drafts=[_draft("d_001")])

    with pytest.raises(NoSuchDraftError) as raised:
        _use_case(workflows, FakeStore(), CapturingProvider()).execute(
            ResumeCreateWorkflowCommand()
        )

    assert raised.value.catalogue_key == "error.draft.no_session"


def test_a_client_that_cannot_reopen_is_refused() -> None:
    provider = CapturingProvider(can_resume=False)
    workflows = FakeWorkflows(drafts=[_draft("d_001")])
    store = FakeStore(sessions=[_authoring_session("d_001", client="codex")])

    with pytest.raises(NoSuchDraftError) as raised:
        _use_case(workflows, store, provider).execute(ResumeCreateWorkflowCommand())

    assert raised.value.catalogue_key == "error.draft.resume_unsupported"
