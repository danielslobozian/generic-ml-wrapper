# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The authoring job is recorded like any other and left out of `gmlw jobs` by name.

There is no second kind of job and no second store. Authoring records into the one
ledger, under the one name the system chooses for itself, and the listing use case is
the only thing that treats that name differently.
"""

from pathlib import Path

from _delete_doubles import FakeSessionLock

from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnostics
from generic_ml_wrapper.adapter.outbound.i18n.json_catalog_localizer import (
    JsonCatalogLocalizerFactory,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_source import (
    FilesystemWorkflowSource,
)
from generic_ml_wrapper.application.domain.model.authoring_job import AuthoringJob
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.localizer import Localizer
from generic_ml_wrapper.application.port.inbound.new_workflow import NewWorkflowCommand
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller, CliCallerProvider
from generic_ml_wrapper.application.usecase.hook_runner import HookRunner
from generic_ml_wrapper.application.usecase.launch import LaunchSequence
from generic_ml_wrapper.application.usecase.list_jobs import ListJobsUseCase
from generic_ml_wrapper.application.usecase.new_workflow import NewWorkflowUseCase


class _NoLaunchProvider(CliCallerProvider):
    def for_run(self, run: RunContext) -> CliCaller:
        return _NoLaunch(run)


class _NoLaunch(CliCaller):
    def start_client(self) -> int:
        return 0


def test_authoring_is_recorded_but_left_out_of_the_job_listing(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.db")
    new_workflow = NewWorkflowUseCase(
        workflows=FilesystemWorkflowSource(tmp_path / "workflows"),
        store=SqliteSessionStore(ledger),
        callers=_NoLaunchProvider(),
        uuid_factory=lambda: "u",
        launch=LaunchSequence(
            HookRunner((), NullDiagnostics(), _localizer()),
            NullDiagnostics(),
            _localizer(),
            FakeSessionLock(),
        ),
    )
    new_workflow.execute(NewWorkflowCommand(label="doc-review", client="claude"))

    # The session is really there: the store keeps no secrets, so deleting it is possible.
    # Always as create-workflow -- the target name is a seed, decided at the end.
    assert SqliteSessionStore(ledger).jobs() == [AuthoringJob.NAME]
    # `gmlw jobs` leaves that one name out, and it is the only name it leaves out.
    assert ListJobsUseCase(SqliteSessionStore(ledger)).execute() == []


def test_the_listing_hides_nothing_else(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.db")
    store = SqliteSessionStore(ledger)
    store.record(
        Session(
            session_id="PROJ-482_001",
            job="PROJ-482",
            client="claude",
            uuid=None,
            cwd="/work",
            resumable=True,
        )
    )

    assert [summary.job for summary in ListJobsUseCase(store).execute()] == ["PROJ-482"]


def _localizer() -> Localizer:
    """The real English catalogue: these tests assert behaviour, not translations."""
    return JsonCatalogLocalizerFactory().load("en")
