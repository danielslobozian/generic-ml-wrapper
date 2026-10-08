# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the StartJob use case, driven by fakes for its outbound ports."""

import os
import zipfile
from pathlib import Path

import pytest
from _conformance import InMemoryJobTagStore

from generic_ml_wrapper.adapter.outbound.attachment.filesystem_attachment_store import (
    FilesystemAttachmentStore,
    folder_hash,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.application.domain.model.attachment import AttachmentError
from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import Draft, DraftMarker
from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.domain.service.hook import Hook, HookContext, HookPhase
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJobCommand,
    UnknownWorkflowError,
)
from generic_ml_wrapper.application.port.outbound.attachment_store import AttachmentStorePort
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller, CliCallerProvider
from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.import_attachment import ImportAttachmentUseCase
from generic_ml_wrapper.application.usecase.start_job import StartJobUseCase

# A quoted value once split, per platform: Windows splits in non-posix mode on purpose, so
# the quotes stay inside the token there. See ``common.client_args`` for why.
QUOTED_PATH = "/two words" if os.name != "nt" else '"/two words"'


class FakeStore(SessionStorePort):
    def __init__(
        self,
        latest: Session | None = None,
        ids: list[str] | None = None,
        sessions: list[Session] | None = None,
    ) -> None:
        self.recorded: list[Session] = []
        self.bound: list[tuple[str, str, str]] = []
        self._latest = latest
        self._ids = ids or []
        self._sessions = sessions or []

    def jobs(self) -> list[str]:
        return []

    def bind_uuid(self, job: str, session_id: str, uuid: str) -> None:
        self.bound.append((job, session_id, uuid))

    def sessions_for_job(self, job: str) -> list[Session]:
        return self._sessions

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

    def catalog(self) -> list[Workflow]:
        return []

    def create(self, name: str) -> str:
        raise NotImplementedError

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
        raise NotImplementedError

    def compile(
        self,
        mode: CompileMode,
        name: str | None = None,
        job: str | None = None,
        attachment: str | None = None,
    ) -> str:
        self.compiled.append((mode, name))
        if mode is CompileMode.ATTACHMENT:
            return f"{self._baseline}\n\n\n{attachment}"
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


def _use_case(  # noqa: PLR0913, PLR0917  (mirrors the use case's full port set, plus the greeting)
    store: FakeStore,
    provider: FakeProvider,
    workflows: FakeWorkflows | None = None,
    credentials: FakeCredentials | None = None,
    hooks: HookRunner | None = None,
    greeting: str | None = None,
    capability_card: str | None = None,
    client_args: dict[str, str] | None = None,
    tags: InMemoryJobTagStore | None = None,
    attachments: AttachmentStorePort | None = None,
) -> StartJobUseCase:
    return StartJobUseCase(
        store=store,
        workflows=workflows or FakeWorkflows(),
        callers=provider,
        uuid_factory=lambda: "fixed-uuid",
        cwd_factory=lambda: "/work/svc-a",
        credentials=credentials or FakeCredentials(),
        hooks=hooks or HookRunner(()),
        greeting=lambda: greeting,
        capability_card=lambda: capability_card,
        tags=tags or InMemoryJobTagStore(),
        # configured per client; a client with no entry has no arguments
        client_args=lambda client: (client_args or {}).get(client, ""),
        attachments=attachments,
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


def test_resume_session_reopens_the_named_session_in_its_folder() -> None:
    sessions = [
        Session("JOB-1_001", "JOB-1", "claude", "uuid-1", cwd="/work/svc-a"),
        Session("JOB-1_002", "JOB-1", "cursor", "uuid-2", cwd="/work/svc-b"),
    ]
    provider = FakeProvider()
    _use_case(FakeStore(sessions=sessions), provider).execute(
        StartJobCommand(job="JOB-1", client="claude", resume_session="JOB-1_002")
    )

    assert provider.run is not None
    assert provider.run.resume is True
    assert provider.run.session_id == "JOB-1_002"
    assert provider.run.client == "cursor"  # the session's client, not the command's
    assert provider.run.cwd == "/work/svc-b"  # relaunch in the session's folder


def test_resume_session_wins_over_resume_latest() -> None:
    sessions = [Session("JOB-1_001", "JOB-1", "claude", "u1", cwd="/a")]
    latest = Session("JOB-1_009", "JOB-1", "claude", "u9", cwd="/z")
    provider = FakeProvider()
    _use_case(FakeStore(latest=latest, sessions=sessions), provider).execute(
        StartJobCommand(
            job="JOB-1", client="claude", resume_latest=True, resume_session="JOB-1_001"
        )
    )

    assert provider.run is not None
    assert provider.run.session_id == "JOB-1_001"  # specific id beats "latest"


def test_resume_session_unknown_id_falls_back_to_a_new_session() -> None:
    provider = FakeProvider()
    store = FakeStore(sessions=[Session("JOB-1_001", "JOB-1", "claude", "u1")])
    _use_case(store, provider).execute(
        StartJobCommand(job="JOB-1", client="claude", resume_session="JOB-1_404")
    )

    assert provider.run is not None
    assert provider.run.resume is False  # unknown id -> mint a new session
    assert len(store.recorded) == 1


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
    assert workflows.seeded is False  # refused before the shared base was installed


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

    with pytest.raises(ResumeNotSupportedError) as excinfo:
        use_case.execute(StartJobCommand(job="JOB-1", client="codex", resume_latest=True))

    assert excinfo.value.params["client"] == "codex"
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


# ── passthrough launch arguments ──
def test_configured_args_reach_the_run_split_into_tokens() -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider()
    _use_case(store, provider, client_args={"claude": '--yolo --add-dir "/two words"'}).execute(
        StartJobCommand(job="JOB-1", client="claude")
    )
    assert provider.run is not None
    # Quoting survives per platform — see QUOTED_PATH's note in test_client_args.
    assert provider.run.client_args == ("--yolo", "--add-dir", QUOTED_PATH)


def test_a_client_with_no_configured_args_gets_none() -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider()
    _use_case(store, provider, client_args={"codex": "--profile work"}).execute(
        StartJobCommand(job="JOB-1", client="claude")
    )
    assert provider.run is not None
    assert provider.run.client_args == ()


def test_an_explicit_override_replaces_the_configured_value() -> None:
    # The flag names the arguments for *this* launch; it does not add to the configured
    # ones, so a user can deliberately launch without them.
    store = FakeStore(ids=[])
    provider = FakeProvider()
    _use_case(store, provider, client_args={"claude": "--yolo"}).execute(
        StartJobCommand(job="JOB-1", client="claude", client_args="--verbose")
    )
    assert provider.run is not None
    assert provider.run.client_args == ("--verbose",)


def test_an_empty_override_launches_with_no_arguments() -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider()
    _use_case(store, provider, client_args={"claude": "--yolo"}).execute(
        StartJobCommand(job="JOB-1", client="claude", client_args="")
    )
    assert provider.run is not None
    assert provider.run.client_args == ()


def test_a_resume_takes_the_arguments_of_the_sessions_own_client() -> None:
    # The decisive case for keying the table by client: the run's client on a resume comes
    # from the stored session, not the command, so a resumed codex session must never be
    # handed the flags configured for claude.
    recorded = Session("JOB-1_001", "JOB-1", "codex", "u-1", cwd="/work/svc-a")
    store = FakeStore(latest=recorded, sessions=[recorded])
    provider = FakeProvider()
    _use_case(
        store, provider, client_args={"claude": "--dangerously-skip-permissions", "codex": "--ask"}
    ).execute(StartJobCommand(job="JOB-1", client="claude", resume_latest=True))
    assert provider.run is not None
    assert provider.run.client == "codex"
    assert provider.run.client_args == ("--ask",)


# ── the recorded `resumable` comes from the caller, not from the client's name ──
def test_a_session_is_recorded_resumable_when_its_caller_says_so() -> None:
    # The cursor-mitm case end to end: the client name is unknown to the built-in catalog,
    # so the old lookup recorded resumable=False and every listing showed it that way,
    # even though the adapter could reopen the session perfectly well.
    store = FakeStore(ids=[])
    provider = FakeProvider(can_resume=True)
    _use_case(store, provider).execute(StartJobCommand(job="JOB-1", client="cursor-mitm"))
    assert store.recorded[0].resumable is True


def test_a_session_is_recorded_unresumable_when_its_caller_says_so() -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider(can_resume=False)
    _use_case(store, provider).execute(StartJobCommand(job="JOB-1", client="cursor-mitm"))
    assert store.recorded[0].resumable is False


def test_the_recorded_flag_matches_what_the_resume_gate_will_ask() -> None:
    # One answer, asked twice: if the stored flag and the gate could disagree, a session
    # would either display as resumable and then be refused, or the reverse.
    for declared in (True, False):
        store = FakeStore(ids=[])
        provider = FakeProvider(can_resume=declared)
        _use_case(store, provider).execute(StartJobCommand(job="JOB-1", client="anything"))
        assert store.recorded[0].resumable is declared


def test_the_workflow_is_recorded_on_the_session_it_started() -> None:
    store = FakeStore()
    _use_case(store, FakeProvider(), FakeWorkflows(present="doc-review")).execute(
        StartJobCommand(job="JOB-1", client="claude", workflow="doc-review")
    )
    assert [session.workflow for session in store.recorded] == ["doc-review"]


def test_a_plain_start_records_no_workflow() -> None:
    store = FakeStore()
    _use_case(store, FakeProvider()).execute(StartJobCommand(job="JOB-1", client="claude"))
    assert [session.workflow for session in store.recorded] == [None]


def test_start_tags_the_job_once_its_session_is_recorded() -> None:
    tags = InMemoryJobTagStore()
    _use_case(FakeStore(), FakeProvider(), tags=tags).execute(
        StartJobCommand(job="PAY-1", client="claude", tags=("Sprint-42", "payments"))
    )
    assert tags.tags_by_job() == {"PAY-1": ("payments", "sprint-42")}


def test_an_invalid_tag_is_refused_before_a_session_is_spent() -> None:
    store = FakeStore()
    provider = FakeProvider()
    with pytest.raises(IdentifierError):
        _use_case(store, provider).execute(
            StartJobCommand(job="PAY-1", client="claude", tags=("not a tag",))
        )
    assert store.recorded == []
    assert provider.run is None


def _store_with(tmp_path: Path, *versions: str) -> FilesystemAttachmentStore:
    store = FilesystemAttachmentStore(tmp_path / "attachments", Ledger(tmp_path / "ledger.db"))
    for version in versions:
        archive = tmp_path / f"notes-{version}.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr(
                "manifest.yaml", f"name: notes\nversion: {version}\nmain_md_file: main.md\n"
            )
            zipped.writestr("main.md", f"Notes {version}: read more/details.md when needed.\n")
            zipped.writestr("more/details.md", "Details.\n")
        ImportAttachmentUseCase(store).execute(str(archive))
    return store


def test_an_attachment_follows_the_baseline_and_opens_the_session(tmp_path: Path) -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider()
    workflows = FakeWorkflows()
    attachments = _store_with(tmp_path, "1.0.0")
    credentials = FakeCredentials({"notes": {"NOTES_TOKEN": "t"}})

    _use_case(store, provider, workflows, credentials=credentials, attachments=attachments).execute(
        StartJobCommand(job="JOB-1", client="claude", attachment="notes")
    )

    run = provider.run
    assert run is not None
    folder = tmp_path / "attachments" / "notes" / "1.0.0"
    assert workflows.compiled == [(CompileMode.ATTACHMENT, None)]
    assert run.context is not None
    assert run.context.startswith("BASELINE\n\n\n## Attachment: notes 1.0.0\n\n")
    assert f"Its files are in {folder}." in run.context
    assert run.context.endswith("Notes 1.0.0: read more/details.md when needed.")
    assert run.kickoff == (
        "This session on JOB-1 runs with the attachment notes 1.0.0. Begin as its text says."
    )
    assert run.env == (("NOTES_TOKEN", "t"),)
    assert run.extra_dirs == (str(tmp_path / "attachments"),)
    recorded = store.recorded[0]
    assert (recorded.attachment, recorded.attachment_version) == ("notes", "1.0.0")
    assert recorded.attachment_hash == folder_hash(folder)
    assert recorded.workflow is None


def test_an_attachment_defaults_to_its_highest_version(tmp_path: Path) -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider()
    attachments = _store_with(tmp_path, "2.9.0", "2.10.0", "1.0.0")

    _use_case(store, provider, attachments=attachments).execute(
        StartJobCommand(job="JOB-1", client="claude", attachment="notes")
    )

    assert store.recorded[0].attachment_version == "2.10.0"


def test_an_attachment_version_can_be_chosen(tmp_path: Path) -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider()
    attachments = _store_with(tmp_path, "1.0.0", "2.0.0")

    _use_case(store, provider, attachments=attachments).execute(
        StartJobCommand(
            job="JOB-1", client="claude", attachment="notes", attachment_version="1.0.0"
        )
    )

    assert store.recorded[0].attachment_version == "1.0.0"
    assert provider.run is not None
    assert "Notes 1.0.0" in (provider.run.context or "")


@pytest.mark.parametrize(
    ("name", "version", "key"),
    [
        ("missing", None, "error.attachment.not_found"),
        ("notes", "9.0.0", "error.attachment.version_not_found"),
    ],
)
def test_an_unknown_attachment_is_refused_before_a_session_is_spent(
    tmp_path: Path, name: str, version: str | None, key: str
) -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider()
    attachments = _store_with(tmp_path, "1.0.0")

    with pytest.raises(AttachmentError) as raised:
        _use_case(store, provider, attachments=attachments).execute(
            StartJobCommand(
                job="JOB-1", client="claude", attachment=name, attachment_version=version
            )
        )

    assert raised.value.catalogue_key == key
    assert store.recorded == []
    assert provider.log == []


def test_a_changed_attachment_is_refused_before_a_session_is_spent(tmp_path: Path) -> None:
    store = FakeStore(ids=[])
    provider = FakeProvider()
    attachments = _store_with(tmp_path, "1.0.0")
    folder = tmp_path / "attachments" / "notes" / "1.0.0"
    folder.chmod(0o755)
    (folder / "extra.md").write_text("x")

    with pytest.raises(AttachmentError) as raised:
        _use_case(store, provider, attachments=attachments).execute(
            StartJobCommand(job="JOB-1", client="claude", attachment="notes")
        )

    assert raised.value.catalogue_key == "error.attachment.invalid"
    assert store.recorded == []


def test_without_a_store_an_attachment_is_not_found() -> None:
    store = FakeStore(ids=[])
    with pytest.raises(AttachmentError):
        _use_case(store, FakeProvider()).execute(
            StartJobCommand(job="JOB-1", client="claude", attachment="notes")
        )


def test_resuming_an_attachment_session_reopens_the_store(tmp_path: Path) -> None:
    attachments = _store_with(tmp_path, "1.0.0")
    session = Session(
        "JOB-1_001",
        "JOB-1",
        "claude",
        "u-1",
        "/work",
        attachment="notes",
        attachment_version="1.0.0",
    )
    store = FakeStore(latest=session, ids=["JOB-1_001"])
    provider = FakeProvider()

    _use_case(store, provider, attachments=attachments).execute(
        StartJobCommand(job="JOB-1", client="claude", resume_latest=True)
    )

    assert provider.run is not None
    assert provider.run.resume is True
    assert provider.run.context is None
    assert provider.run.extra_dirs == (str(tmp_path / "attachments"),)


def test_resuming_a_plain_session_opens_nothing(tmp_path: Path) -> None:
    session = Session("JOB-1_001", "JOB-1", "claude", "u-1", "/work")
    store = FakeStore(latest=session, ids=["JOB-1_001"])
    provider = FakeProvider()

    _use_case(store, provider, attachments=_store_with(tmp_path)).execute(
        StartJobCommand(job="JOB-1", client="claude", resume_latest=True)
    )

    assert provider.run is not None
    assert provider.run.extra_dirs == ()
