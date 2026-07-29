# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the NewWorkflow use case, driven by fakes."""

import pytest

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import Draft, DraftMarker
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflowCommand,
    NoSuchDraftError,
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
    def __init__(
        self,
        *,
        existing: bool = False,
        marker: DraftMarker = _UNFINISHED,
        drafts: list[Draft] | None = None,
    ) -> None:
        self.seeded = False
        self.draft_key: str | None = None
        self.deployed: tuple[str, str] | None = None
        self._existing = existing
        self._marker = marker
        self._drafts = drafts or []

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

    def drafts(self) -> list[Draft]:
        return list(self._drafts)

    def create_draft(self, key: str) -> str:
        self.draft_key = key
        return f"/drafts/{key}"

    def read_draft_marker(self, draft_path: str) -> DraftMarker:
        return self._marker

    def deploy_draft(self, draft_path: str, name: str) -> str:
        self.deployed = (draft_path, name)
        return f"/workflows/{name}"

    def meta_guide(self) -> str:
        return "GUIDE-LAYER"

    def compile(self, mode: CompileMode, name: str | None = None, job: str | None = None) -> str:
        return f"CONTEXT<{mode.value}:{name}>"


class FakeStore(SessionStorePort):
    def __init__(self, sessions: list[Session] | None = None) -> None:
        self.recorded: list[Session] = []
        self.sessions = sessions or []

    def jobs(self) -> list[str]:
        return []

    def sessions_for_job(self, job: str) -> list[Session]:
        return list(self.sessions)

    def bind_uuid(self, job: str, session_id: str, uuid: str) -> None:
        return None

    def record(self, session: Session) -> None:
        self.recorded.append(session)

    def ids_for_job(self, job: str) -> list[str]:
        return []

    def latest_for_job(self, job: str) -> Session | None:
        return None


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


def test_guided_appends_the_facilitation_layer() -> None:
    workflows = FakeWorkflows(marker=DraftMarker("x", finished=True))
    provider = CapturingProvider()

    _use_case(workflows, FakeStore(), provider).execute(
        NewWorkflowCommand(name=None, client="claude", guided=True)
    )

    assert provider.run is not None
    assert "GUIDE-LAYER" in (provider.run.context or "")  # the guide is injected
    assert "draft.md" in (provider.run.kickoff or "")  # kickoff names the distilled files


def test_quick_omits_the_facilitation_layer() -> None:
    workflows = FakeWorkflows(marker=DraftMarker("x", finished=True))
    provider = CapturingProvider()

    _use_case(workflows, FakeStore(), provider).execute(
        NewWorkflowCommand(name=None, client="claude", guided=False)
    )

    assert provider.run is not None
    assert "GUIDE-LAYER" not in (provider.run.context or "")  # not injected -> cheaper


# ── reopening an interrupted draft ──
def _draft(key: str, *, finished: bool = False, name: str | None = None) -> Draft:
    return Draft(key=key, path=f"/drafts/{key}", name=name, finished=finished)


def _authoring_session(key: str, client: str = "claude") -> Session:
    return Session(key, "create-workflow", client, f"uuid-{key}", cwd=f"/drafts/{key}")


def test_a_new_session_records_the_draft_it_runs_in() -> None:
    # Previously left unset, which is what made an interrupted interview unrecoverable:
    # the session claimed no folder, so nothing could relaunch it where its work lives.
    workflows = FakeWorkflows()
    store = FakeStore()
    _use_case(workflows, store, CapturingProvider()).execute(
        NewWorkflowCommand(name=None, client="claude")
    )
    recorded = store.recorded[0]
    assert recorded.cwd == f"/drafts/{recorded.session_id}"
    assert recorded.resumable is True  # the caller said so


def test_resuming_the_latest_draft_reopens_it_in_its_own_folder() -> None:
    workflows = FakeWorkflows(drafts=[_draft("create-workflow_007")])
    store = FakeStore(sessions=[_authoring_session("create-workflow_007")])
    provider = CapturingProvider()

    _use_case(workflows, store, provider).execute(
        NewWorkflowCommand(name=None, client="claude", resume_latest=True)
    )

    assert provider.run is not None
    assert provider.run.resume is True
    assert provider.run.cwd == "/drafts/create-workflow_007"
    assert provider.run.session_id == "create-workflow_007"
    assert provider.run.uuid == "uuid-create-workflow_007"


def test_resuming_does_not_re_inject_the_authoring_context() -> None:
    # The client already holds the interview; re-sending the context would talk over it.
    workflows = FakeWorkflows(drafts=[_draft("create-workflow_007")])
    store = FakeStore(sessions=[_authoring_session("create-workflow_007")])
    provider = CapturingProvider()
    _use_case(workflows, store, provider).execute(
        NewWorkflowCommand(name=None, client="claude", resume_latest=True)
    )
    assert provider.run is not None
    assert provider.run.context is None


def test_resuming_uses_the_sessions_own_client_not_the_commands() -> None:
    # The conversation belongs to the client that held it; reopening it elsewhere would
    # start from nothing.
    workflows = FakeWorkflows(drafts=[_draft("create-workflow_007")])
    store = FakeStore(sessions=[_authoring_session("create-workflow_007", client="cursor")])
    provider = CapturingProvider()
    _use_case(workflows, store, provider).execute(
        NewWorkflowCommand(name=None, client="claude", resume_latest=True)
    )
    assert provider.run is not None
    assert provider.run.client == "cursor"


def test_resuming_a_named_draft_picks_that_one() -> None:
    workflows = FakeWorkflows(drafts=[_draft("create-workflow_009"), _draft("create-workflow_007")])
    store = FakeStore(
        sessions=[
            _authoring_session("create-workflow_009"),
            _authoring_session("create-workflow_007"),
        ]
    )
    provider = CapturingProvider()
    _use_case(workflows, store, provider).execute(
        NewWorkflowCommand(name=None, client="claude", resume_draft="create-workflow_007")
    )
    assert provider.run is not None
    assert provider.run.session_id == "create-workflow_007"


def test_resume_latest_skips_a_finished_draft() -> None:
    # A finished draft is not waiting on the user -- it converged and was blocked from
    # deploying. Reopening it silently would hide that; naming it explicitly still works.
    workflows = FakeWorkflows(
        drafts=[
            _draft("create-workflow_009", finished=True, name="taken"),
            _draft("create-workflow_007"),
        ]
    )
    store = FakeStore(
        sessions=[
            _authoring_session("create-workflow_009"),
            _authoring_session("create-workflow_007"),
        ]
    )
    provider = CapturingProvider()
    _use_case(workflows, store, provider).execute(
        NewWorkflowCommand(name=None, client="claude", resume_latest=True)
    )
    assert provider.run is not None
    assert provider.run.session_id == "create-workflow_007"


def test_resuming_an_unknown_draft_is_refused() -> None:
    workflows = FakeWorkflows(drafts=[_draft("create-workflow_007")])
    store = FakeStore(sessions=[_authoring_session("create-workflow_007")])
    with pytest.raises(NoSuchDraftError):
        _use_case(workflows, store, CapturingProvider()).execute(
            NewWorkflowCommand(name=None, client="claude", resume_draft="create-workflow_404")
        )


def test_resuming_with_no_drafts_is_refused() -> None:
    with pytest.raises(NoSuchDraftError):
        _use_case(FakeWorkflows(), FakeStore(), CapturingProvider()).execute(
            NewWorkflowCommand(name=None, client="claude", resume_latest=True)
        )


def test_a_draft_whose_session_was_never_recorded_is_refused() -> None:
    # Drafts on disk and sessions in the ledger can drift apart; say so rather than
    # relaunching with no client and no uuid.
    workflows = FakeWorkflows(drafts=[_draft("create-workflow_007")])
    with pytest.raises(NoSuchDraftError):
        _use_case(workflows, FakeStore(), CapturingProvider()).execute(
            NewWorkflowCommand(name=None, client="claude", resume_latest=True)
        )


def test_a_resumed_draft_still_deploys_when_it_converges() -> None:
    # The reopened session runs the same _finalize: finishing after a resume must deploy
    # exactly as finishing first time round does.
    workflows = FakeWorkflows(
        marker=DraftMarker("nightly-etl", finished=True), drafts=[_draft("create-workflow_007")]
    )
    store = FakeStore(sessions=[_authoring_session("create-workflow_007")])
    result = _use_case(workflows, store, CapturingProvider()).execute(
        NewWorkflowCommand(name=None, client="claude", resume_latest=True)
    )
    assert result.outcome is WorkflowOutcome.DEPLOYED
    assert workflows.deployed == ("/drafts/create-workflow_007", "nightly-etl")


def test_a_draft_on_a_client_that_cannot_reopen_is_refused() -> None:
    # Better to say so than to relaunch a client that will start an empty session.
    workflows = FakeWorkflows(drafts=[_draft("create-workflow_007")])
    store = FakeStore(sessions=[_authoring_session("create-workflow_007", client="vibe")])
    with pytest.raises(NoSuchDraftError):
        _use_case(workflows, store, CapturingProvider(can_resume=False)).execute(
            NewWorkflowCommand(name=None, client="claude", resume_latest=True)
        )
