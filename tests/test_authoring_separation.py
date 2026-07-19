# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Authoring sessions carry the ``authoring`` kind and never pollute `gmlw jobs`."""

from pathlib import Path

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_source import (
    FilesystemWorkflowSource,
)
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.port.inbound.new_workflow import NewWorkflowCommand
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller, CliCallerProvider
from generic_ml_wrapper.application.usecase.list_jobs import ListJobsUseCase
from generic_ml_wrapper.application.usecase.new_workflow import NewWorkflowUseCase


class _NoLaunchProvider(CliCallerProvider):
    def for_run(self, run: RunContext) -> CliCaller:
        return _NoLaunch(run)


class _NoLaunch(CliCaller):
    def start_client(self) -> int:
        return 0


def test_authoring_is_hidden_from_work_jobs(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.db")
    new_workflow = NewWorkflowUseCase(
        workflows=FilesystemWorkflowSource(tmp_path / "workflows"),
        store=SqliteSessionStore(ledger, kind="authoring"),
        callers=_NoLaunchProvider(),
        uuid_factory=lambda: "u",
        hooks=HookRunner(()),
    )
    new_workflow.execute(NewWorkflowCommand(name="doc-review", client="claude"))

    # `gmlw jobs` reads the work kind only -- untouched by authoring.
    assert ListJobsUseCase(SqliteSessionStore(ledger, kind="work")).execute() == []
    # The authoring session landed under the authoring kind, always as create-workflow
    # (the target name is a seed, decided at the end -- sessions accumulate here).
    assert SqliteSessionStore(ledger, kind="authoring").jobs() == ["create-workflow"]
