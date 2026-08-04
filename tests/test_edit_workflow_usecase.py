# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the EditWorkflow use case, driven by fakes."""

import pytest
from _delete_doubles import FakeSessionLock

from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnostics
from generic_ml_wrapper.adapter.outbound.i18n.json_catalog_localizer import (
    JsonCatalogLocalizerFactory,
)
from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import Draft, DraftMarker
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.domain.service.localizer import Localizer
from generic_ml_wrapper.application.port.inbound.edit_workflow import (
    EditWorkflowCommand,
    NoEditToResumeError,
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.new_workflow import WorkflowNameError
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller, CliCallerProvider
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.edit_workflow import EditWorkflowUseCase
from generic_ml_wrapper.application.usecase.hook_runner import HookRunner
from generic_ml_wrapper.application.usecase.launch import LaunchSequence


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

    def catalog(self) -> list[Workflow]:
        return []

    def create(self, name: str) -> str:
        self.created = name  # must never be called when editing
        return f"/workflows/{name}"

    def folder(self, name: str) -> str:
        return f"/workflows/{name}"

    def drafts(self) -> list[Draft]:
        raise NotImplementedError

    def create_draft(self, key: str) -> str:
        raise NotImplementedError

    def read_draft_marker(self, draft_path: str) -> DraftMarker:
        raise NotImplementedError

    def deploy_draft(
        self, draft_path: str, name: str, label: str, description: str, created: str
    ) -> str:
        raise NotImplementedError

    def meta_guide(self) -> str:
        return "GUIDE-LAYER"

    def compile(self, mode: CompileMode, name: str | None = None, job: str | None = None) -> str:
        return f"CONTEXT<{mode.value}:{name}>"


class FakeStore(SessionStorePort):
    def __init__(
        self, latest: Session | None = None, sessions: list[Session] | None = None
    ) -> None:
        self.recorded: list[Session] = []
        self._latest = latest
        self._sessions = sessions if sessions is not None else ([latest] if latest else [])

    def jobs(self) -> list[str]:
        return []

    def sessions_for_job(self, job: str) -> list[Session]:
        return list(self._sessions)

    def bind_uuid(self, job: str, session_id: str, uuid: str) -> None:
        return None

    def record(self, session: Session) -> None:
        self.recorded.append(session)

    def ids_for_job(self, job: str) -> list[str]:
        return []

    def latest_for_job(self, job: str) -> Session | None:
        return self._latest


class CapturingProvider(CliCallerProvider):
    def __init__(self, *, can_resume: bool = True) -> None:
        self.run: RunContext | None = None
        self._can_resume = can_resume

    def for_run(self, run: RunContext) -> CliCaller:
        self.run = run
        return _NoopCaller(run, can_resume=self._can_resume)


class _NoopCaller(CliCaller):
    def __init__(self, run: RunContext, *, can_resume: bool = True) -> None:
        super().__init__(run)
        self._can_resume = can_resume

    def can_resume(self) -> bool:
        return self._can_resume

    def start_client(self) -> int:
        return 0


def _use_case(
    workflows: FakeWorkflows, store: FakeStore, provider: CapturingProvider
) -> EditWorkflowUseCase:
    return EditWorkflowUseCase(
        workflows,
        store,
        provider,
        uuid_factory=lambda: "fixed-uuid",
        launch=LaunchSequence(
            HookRunner((), NullDiagnostics(), _localizer()),
            NullDiagnostics(),
            _localizer(),
            FakeSessionLock(),
        ),
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
    # Filed under the authoring job, not under a job named after the workflow: creating and
    # editing are one history. Which workflow was edited is carried by the folder below.
    assert store.recorded[0].job == "create-workflow"
    assert provider.run is not None
    assert provider.run.cwd == "/workflows/doc-review"
    assert provider.run.context == "CONTEXT<authoring:create-workflow>"
    assert "editing" in (provider.run.kickoff or "")
    assert "doc-review" in (provider.run.kickoff or "")


def test_guided_edit_appends_the_facilitation_layer() -> None:
    workflows = FakeWorkflows(existing=True)
    provider = CapturingProvider()

    _use_case(workflows, FakeStore(), provider).execute(
        EditWorkflowCommand(name="doc-review", client="claude", guided=True)
    )

    assert provider.run is not None
    assert "GUIDE-LAYER" in (provider.run.context or "")  # the guide layers onto the edit


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


# ── reopening an interrupted edit ──
def test_an_edit_records_the_folder_it_ran_in() -> None:
    # Previously unset, leaving an interrupted edit with no folder to return to.
    workflows = FakeWorkflows(existing=True)
    store = FakeStore()
    _use_case(workflows, store, CapturingProvider()).execute(
        EditWorkflowCommand(name="nightly-etl", client="claude")
    )
    recorded = store.recorded[0]
    assert recorded.cwd == "/workflows/nightly-etl"
    assert recorded.resumable is True


def test_resuming_an_edit_reopens_the_latest_session_in_the_workflow_folder() -> None:
    prior = Session(
        "nightly-etl_001", "nightly-etl", "claude", "uuid-1", cwd="/workflows/nightly-etl"
    )
    workflows = FakeWorkflows(existing=True)
    provider = CapturingProvider()
    _use_case(workflows, FakeStore(latest=prior), provider).execute(
        EditWorkflowCommand(name="nightly-etl", client="claude", resume_latest=True)
    )
    assert provider.run is not None
    assert provider.run.resume is True
    assert provider.run.session_id == "nightly-etl_001"
    assert provider.run.uuid == "uuid-1"
    assert provider.run.cwd == "/workflows/nightly-etl"


def test_resuming_an_edit_does_not_re_inject_the_context() -> None:
    prior = Session(
        "nightly-etl_001", "nightly-etl", "claude", "uuid-1", cwd="/workflows/nightly-etl"
    )
    provider = CapturingProvider()
    _use_case(FakeWorkflows(existing=True), FakeStore(latest=prior), provider).execute(
        EditWorkflowCommand(name="nightly-etl", client="claude", resume_latest=True)
    )
    assert provider.run is not None
    assert provider.run.context is None


def test_resuming_an_edit_uses_the_sessions_own_client() -> None:
    prior = Session(
        "nightly-etl_001", "nightly-etl", "cursor", "uuid-1", cwd="/workflows/nightly-etl"
    )
    provider = CapturingProvider()
    _use_case(FakeWorkflows(existing=True), FakeStore(latest=prior), provider).execute(
        EditWorkflowCommand(name="nightly-etl", client="claude", resume_latest=True)
    )
    assert provider.run is not None
    assert provider.run.client == "cursor"


def test_resuming_an_edit_with_no_prior_session_is_refused() -> None:
    with pytest.raises(NoEditToResumeError):
        _use_case(FakeWorkflows(existing=True), FakeStore(), CapturingProvider()).execute(
            EditWorkflowCommand(name="nightly-etl", client="claude", resume_latest=True)
        )


def test_resuming_an_edit_on_a_client_that_cannot_reopen_is_refused() -> None:
    prior = Session(
        "nightly-etl_001", "nightly-etl", "vibe", "uuid-1", cwd="/workflows/nightly-etl"
    )
    with pytest.raises(NoEditToResumeError):
        _use_case(
            FakeWorkflows(existing=True),
            FakeStore(latest=prior),
            CapturingProvider(can_resume=False),
        ).execute(EditWorkflowCommand(name="nightly-etl", client="claude", resume_latest=True))


def test_resuming_an_unknown_workflow_is_still_refused_as_unknown() -> None:
    # The name check runs first: "no such workflow" is more useful than "nothing to resume".
    with pytest.raises(WorkflowNotFoundError):
        _use_case(FakeWorkflows(existing=False), FakeStore(), CapturingProvider()).execute(
            EditWorkflowCommand(name="ghost", client="claude", resume_latest=True)
        )


def test_resuming_an_edit_ignores_run_sessions_filed_under_the_same_job() -> None:
    # `gmlw run <workflow>` and `gmlw workflow edit <workflow>` both file under a job
    # named after the workflow. Reopening a run here would relaunch it in the workflow
    # folder rather than where it actually ran, and a cwd-scoped client would find
    # nothing. Caught on real data: the job's newest session was a run in the repo root.
    an_edit = Session(
        "nightly-etl_001", "nightly-etl", "claude", "edit-uuid", cwd="/workflows/nightly-etl"
    )
    a_later_run = Session(
        "nightly-etl_002", "nightly-etl", "claude", "run-uuid", cwd="/home/me/code"
    )
    provider = CapturingProvider()
    _use_case(
        FakeWorkflows(existing=True),
        FakeStore(sessions=[an_edit, a_later_run]),
        provider,
    ).execute(EditWorkflowCommand(name="nightly-etl", client="claude", resume_latest=True))
    assert provider.run is not None
    assert provider.run.uuid == "edit-uuid"


def test_an_edit_recorded_before_its_folder_was_stored_is_not_resumed() -> None:
    # Its cwd is None, so it cannot be told apart from a run; refusing beats reopening
    # the wrong conversation.
    older = Session("nightly-etl_001", "nightly-etl", "claude", "uuid-1")
    with pytest.raises(NoEditToResumeError):
        _use_case(
            FakeWorkflows(existing=True), FakeStore(sessions=[older]), CapturingProvider()
        ).execute(EditWorkflowCommand(name="nightly-etl", client="claude", resume_latest=True))


def _localizer() -> Localizer:
    """The real English catalogue: these tests assert behaviour, not translations."""
    return JsonCatalogLocalizerFactory().load("en")
