# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the CLI inbound adapter."""

import io
import json
import platform
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.inbound.tui import menu_app as tui
from generic_ml_wrapper.adapter.outbound.bootstrap.toml_client_catalog import (
    TomlClientCatalogAdapter,
)
from generic_ml_wrapper.adapter.outbound.config import toml_config_reader
from generic_ml_wrapper.application.domain.model.axis_kind import AxisKind
from generic_ml_wrapper.application.domain.model.axis_selection import AxisSelection
from generic_ml_wrapper.application.domain.model.client_info import ClientInfo
from generic_ml_wrapper.application.domain.model.client_settings_unusable_error import (
    ClientSettingsUnusableError,
)
from generic_ml_wrapper.application.domain.model.launch_location import (
    LaunchLocation,
    LaunchLocationProblem,
)
from generic_ml_wrapper.application.domain.model.migration_report import MigrationReport
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.domain.model.session_cost import SessionCost
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.port.inbound.bootstrap import BootstrapUseCase
from generic_ml_wrapper.application.port.inbound.check_client_ready import (
    CheckClientReadyUseCase,
    ClientReadiness,
)
from generic_ml_wrapper.application.port.inbound.check_launch_location import (
    CheckLaunchLocationUseCase,
)
from generic_ml_wrapper.application.port.inbound.config_commands import ConfigCommandsUseCase
from generic_ml_wrapper.application.port.inbound.create_axis import (
    AxisExistsError,
    CreateAxisCommand,
    CreateAxisResult,
    CreateAxisUseCase,
)
from generic_ml_wrapper.application.port.inbound.delete_jobs import DeleteJobsUseCase, JobFootprint
from generic_ml_wrapper.application.port.inbound.delete_sessions import (
    DeleteSessionsUseCase,
    NoSuchJobError,
    NoSuchSessionError,
    SessionFootprint,
)
from generic_ml_wrapper.application.port.inbound.edit_workflow import (
    EditWorkflowCommand,
    EditWorkflowUseCase,
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.export_usage import (
    ExportUsageUseCase,
    ModelTotal,
    TurnRow,
    UsageReport,
)
from generic_ml_wrapper.application.port.inbound.export_workflow import ExportWorkflowUseCase
from generic_ml_wrapper.application.port.inbound.import_workflow import (
    ArchiveUnreadableError,
    ImportOutcome,
    ImportWorkflowResult,
    ImportWorkflowUseCase,
)
from generic_ml_wrapper.application.port.inbound.init import InitOutcome, InitUseCase
from generic_ml_wrapper.application.port.inbound.list_clients import (
    ClientStatus,
    ListClientsUseCase,
)
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary, ListJobsUseCase
from generic_ml_wrapper.application.port.inbound.list_launch_clients import (
    LaunchClient,
    ListLaunchClientsUseCase,
)
from generic_ml_wrapper.application.port.inbound.list_personas import ListPersonasUseCase
from generic_ml_wrapper.application.port.inbound.list_plugins import ListPluginsUseCase
from generic_ml_wrapper.application.port.inbound.list_sessions import (
    ListSessionsUseCase,
    SessionSummary,
)
from generic_ml_wrapper.application.port.inbound.list_workflow_catalog import (
    ListWorkflowCatalogUseCase,
)
from generic_ml_wrapper.application.port.inbound.list_workflows import ListWorkflowsUseCase
from generic_ml_wrapper.application.port.inbound.migrate_layout import MigrateLayoutUseCase
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflowCommand,
    NewWorkflowResult,
    NewWorkflowUseCase,
    WorkflowExistsError,
    WorkflowOutcome,
)
from generic_ml_wrapper.application.port.inbound.render_greeting import RenderGreetingUseCase
from generic_ml_wrapper.application.port.inbound.render_statusline import RenderStatuslineUseCase
from generic_ml_wrapper.application.port.inbound.set_credential import (
    SetCredentialCommand,
    SetCredentialUseCase,
)
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJobCommand,
    StartJobResult,
    StartJobUseCase,
    UnknownWorkflowError,
)
from generic_ml_wrapper.application.wiring import composition
from generic_ml_wrapper.application.wiring.localization import load_localizer
from generic_ml_wrapper.application.wiring.paths import paths


class _RecordingBootstrap(BootstrapUseCase):
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def execute(self) -> None:
        self._calls.append("init")


def _config_present(*_: object, **__: object) -> bool:
    return True


def _config_absent(*_: object, **__: object) -> bool:
    return False


def _init_done(*_: object, **__: object) -> str | None:
    return "0.4.0"  # the gate sees an initialised install


def _init_absent(*_: object, **__: object) -> str | None:
    return None  # the gate sees an un-initialised (or legacy) install


class _FakeMigrate(MigrateLayoutUseCase):
    def __init__(self, report: MigrationReport | None = None) -> None:
        self._report = report if report is not None else MigrationReport(environment="work")

    def execute(self) -> MigrationReport:
        return self._report


class _CheckClient(CheckClientReadyUseCase):
    def __init__(self, readiness: ClientReadiness | None = None) -> None:
        self._readiness = readiness

    def execute(self, client: str) -> ClientReadiness:
        if self._readiness is not None:
            return self._readiness
        return ClientReadiness(client=client, ready=True, missing=None, installed=(client,))


@pytest.fixture(autouse=True)
def _stub_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep ``main``'s self-init from touching the real ~/.gmlw during CLI tests.

    Also pin ``init_version`` to a value so the gate takes the (stubbed) bootstrap
    branch, not the forced-init branch — init wiring is exercised on its own below —
    and stub the host greeting off so ``start`` tests don't read the real config.
    """
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap([]))
    monkeypatch.setattr(toml_config_reader, "init_version", _init_done)
    monkeypatch.setattr(app, "build_migrate_layout", lambda: _FakeMigrate())  # no-op by default
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient())


def test_implicit_start_rewrites_a_bare_job() -> None:
    assert app._implicit_start(["my-proj"]) == ["start", "my-proj"]
    assert app._implicit_start(["my-proj", "--client", "cursor"]) == [
        "start",
        "my-proj",
        "--client",
        "cursor",
    ]


def test_implicit_start_leaves_commands_flags_and_empty_untouched() -> None:
    assert app._implicit_start(["jobs"]) == ["jobs"]  # a real subcommand
    assert app._implicit_start(["start", "JOB-1"]) == ["start", "JOB-1"]  # explicit start
    assert app._implicit_start(["-h"]) == ["-h"]  # a flag
    assert app._implicit_start([]) == []  # bare gmlw -> help


def test_command_set_entries_are_real_parseable_commands() -> None:
    parser = app.build_parser()
    samples = {
        "init": ["init"],
        "start": ["start"],
        "run": ["run"],
        "jobs": ["jobs"],
        "sessions": ["sessions", "J"],
        "export": ["export", "J"],
        "clients": ["clients"],
        "statusline": ["statusline"],
        "tui": ["tui"],
        "workflow": ["workflow"],
        "persona": ["persona"],
        "plugins": ["plugins"],
        "creds": ["creds"],
        "config": ["config"],
        "environment": ["environment"],
        "role": ["role"],
        "help": ["help"],
    }
    assert set(samples) == app._COMMANDS  # every command has a sample, and vice versa
    for command, argv in samples.items():
        assert parser.parse_args(argv).command == command  # each really parses
        assert app._implicit_start(argv) == argv  # and is never mistaken for a job


def test_bare_job_dispatches_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["my-proj"]) == 0  # `gmlw my-proj`
    assert seen["command"].job == "my-proj"


def test_start_without_a_job_prints_a_friendly_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_start_job", lambda: None)  # must never be reached
    assert app.main(["start"]) == 2
    err = capsys.readouterr().err
    assert "start needs a job" in err
    assert "gmlw jobs" in err  # points at how to see jobs


def test_parser_parses_start_with_flags() -> None:
    args = app.build_parser().parse_args(
        ["start", "JOB-1", "--client", "cursor", "--resume-latest"]
    )
    assert args.command == "start"
    assert args.job == "JOB-1"
    assert args.client == "cursor"
    assert args.resume_latest is True


def test_client_defaults_to_config_when_flag_absent() -> None:
    assert app._client(None) == toml_config_reader.default_client()
    assert app._client("cursor") == "cursor"


def test_bare_gmlw_shows_the_capability_index(capsys: pytest.CaptureFixture[str]) -> None:
    # Initialised install (fixture pins init_version): bare gmlw shows the grouped index,
    # not the raw argparse help.
    assert app.main([]) == 0
    out = capsys.readouterr().out
    assert "launch" in out  # the groups
    assert "inspect" in out
    assert "author" in out
    assert "gmlw help <topic>" in out  # the next-action footer


def test_bare_gmlw_on_a_fresh_install_runs_init(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # First run (no init marker): bare gmlw funnels through the forced setup, not the index.
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)
    seen: list[str] = []

    class _Init(InitUseCase):
        def execute(self) -> InitOutcome:
            seen.append("init")
            return InitOutcome(
                fresh=True,
                language="en",
                name="Dan",
                role=AxisSelection("default", "Default", "Default"),
                environment=AxisSelection("work", "Work", "Work"),
                client="claude",
                persona=None,
                found=["claude"],
            )

    monkeypatch.setattr(app, "build_init", lambda: _Init())
    assert app.main([]) == 0
    assert seen == ["init"]


class _FreshInit(InitUseCase):
    def execute(self) -> InitOutcome:
        return InitOutcome(
            fresh=True,
            language="en",
            name="Dan",
            role=AxisSelection("default", "Default", "Default"),
            environment=AxisSelection("work", "Work", "Work"),
            client="claude",
            persona=None,
            found=["claude"],
        )


def test_bare_gmlw_on_a_tty_opens_the_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    # Initialised install: bare gmlw is the front door — it redirects to the interactive menu
    # (on a real terminal; off one, _tui itself falls back to the capability index).
    called: list[str] = []
    monkeypatch.setattr(app, "_tui", lambda: (called.append("tui"), 0)[1])
    assert app.main([]) == 0
    assert called == ["tui"]


def test_bare_gmlw_fresh_install_runs_init_not_the_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    # First run must win over the menu redirect: init runs, _tui is never reached.
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)
    monkeypatch.setattr(app, "build_init", lambda: _FreshInit())
    tui_called: list[str] = []
    monkeypatch.setattr(app, "_tui", lambda: tui_called.append("tui"))  # must not be called
    assert app.main([]) == 0
    assert tui_called == []


def test_init_prints_the_reinit_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The end of init tells the user how to re-run setup from the menu.
    monkeypatch.setattr(app, "build_init", lambda: _FreshInit())
    assert app.main(["init"]) == 0
    err = capsys.readouterr().err
    assert "Config > Setup" in err  # names the specific menu chain
    assert "gmlw tui" in err


def test_help_lists_topics(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["help"]) == 0
    out = capsys.readouterr().out
    assert "job-vs-workflow" in out
    assert "cost" in out


def test_help_prints_a_topic(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["help", "cost"]) == 0
    assert "metered" in capsys.readouterr().out


def test_help_unknown_topic_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["help", "nope"]) == 2
    assert "no help topic" in capsys.readouterr().err


def test_explicit_help_flag_still_shows_argparse(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        app.main(["--help"])
    assert "a wrapper around an ML coding CLI" in capsys.readouterr().out  # argparse banner


def test_start_dispatches_to_the_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=3, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    exit_code = app.main(["start", "JOB-9", "--resume-latest"])

    assert exit_code == 3
    assert seen["command"] == StartJobCommand(job="JOB-9", client="claude", resume_latest=True)


def test_start_passes_the_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    app.main(["start", "JOB-1", "--workflow", "doc-review"])

    assert seen["command"].workflow == "doc-review"


def test_start_reports_unknown_workflow_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            raise UnknownWorkflowError("unknown workflow: 'missing'")

    monkeypatch.setattr(app, "build_start_job", lambda: FailingUseCase())
    assert app.main(["start", "JOB-1", "--workflow", "missing"]) == 2
    assert "unknown workflow" in capsys.readouterr().out


def test_parser_parses_run() -> None:
    parser = app.build_parser()
    args = parser.parse_args(["run", "etl", "--client", "codex"])
    assert args.command == "run"
    assert args.workflow == "etl"
    assert args.client == "codex"
    bare = parser.parse_args(["run"])  # workflow is optional (a chooser fills it)
    assert bare.command == "run"
    assert bare.workflow is None


def test_run_launches_the_workflow_as_its_own_job(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["run", "nightly-etl"]) == 0
    command = seen["command"]
    assert command.job == "nightly-etl"  # job is named after the workflow
    assert command.workflow == "nightly-etl"
    assert command.resume_latest is False


def test_run_reports_unknown_workflow_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            raise UnknownWorkflowError("unknown workflow: 'missing'")

    monkeypatch.setattr(app, "build_start_job", lambda: FailingUseCase())
    assert app.main(["run", "missing"]) == 2
    assert "unknown workflow" in capsys.readouterr().out


class _FakeWorkflows(ListWorkflowsUseCase):
    def __init__(self, names: list[str]) -> None:
        self._names = names

    def execute(self) -> list[str]:
        return self._names


def test_run_without_a_workflow_off_a_tty_guides(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # No terminal in tests, so the real chooser declines -> we guide instead of blocking.
    monkeypatch.setattr(app, "build_list_workflows", lambda: _FakeWorkflows(["a", "b"]))
    monkeypatch.setattr(app, "build_start_job", lambda: None)  # must never be reached
    assert app.main(["run"]) == 2
    assert "run needs a workflow" in capsys.readouterr().err


def test_run_without_a_workflow_and_none_authored_points_to_authoring(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_list_workflows", lambda: _FakeWorkflows([]))
    monkeypatch.setattr(app, "build_start_job", lambda: None)  # must never be reached
    assert app.main(["run"]) == 2
    assert "no workflows to run" in capsys.readouterr().err


def test_run_interactive_pick_echoes_the_fast_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _Chooser:
        def choose(self, names: list[str], i18n: object | None = None) -> str | None:
            return names[0]

    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_list_workflows", lambda: _FakeWorkflows(["nightly-etl"]))
    monkeypatch.setattr(app, "build_workflow_chooser", lambda: _Chooser())
    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["run"]) == 0
    assert seen["command"].job == "nightly-etl"
    assert "gmlw run nightly-etl" in capsys.readouterr().err  # teaches the fast path


def test_start_reports_resume_not_supported_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            raise ResumeNotSupportedError("session resume not supported on codex")

    monkeypatch.setattr(app, "build_start_job", lambda: FailingUseCase())
    assert app.main(["start", "JOB-1", "--client", "codex", "--resume-latest"]) == 2
    assert "session resume not supported on codex" in capsys.readouterr().out


def test_build_start_job_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_start_job(), StartJobUseCase)


def test_format_jobs_empty() -> None:
    assert "No jobs yet" in app.format_jobs([])


def test_format_jobs_lists_each_summary() -> None:
    text = app.format_jobs(
        [JobSummary("JOB-1", 2), JobSummary("JOB-2", 1)],
    )
    assert "2 job(s):" in text
    assert "JOB-1" in text
    assert "2 session(s)" in text


def test_format_jobs_renders_through_an_injected_localiser() -> None:
    # The renderers take an explicit localiser so app-wide localisation is testable
    # without mutating the process-global active language.
    french = load_localizer("fr")
    assert "Aucun job" in app.format_jobs([], loc=french)
    assert "Aucun usage" in app.format_usage(UsageReport("JOB-1"), loc=french)


def test_jobs_command_prints_the_summaries(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListJobsUseCase):
        def execute(self) -> list[JobSummary]:
            return [JobSummary("JOB-7", 3)]

    monkeypatch.setattr(app, "build_list_jobs", lambda: FakeUseCase())
    assert app.main(["jobs"]) == 0
    out = capsys.readouterr().out
    assert "JOB-7" in out
    assert "3 session(s)" in out


def test_jobs_command_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListJobsUseCase):
        def execute(self) -> list[JobSummary]:
            return [JobSummary("JOB-7", 3)]

    monkeypatch.setattr(app, "build_list_jobs", lambda: FakeUseCase())
    assert app.main(["jobs", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"job": "JOB-7", "session_count": 3}]


class _FakeListClients(ListClientsUseCase):
    def __init__(self, statuses: list[ClientStatus]) -> None:
        self._statuses = statuses

    def execute(self) -> list[ClientStatus]:
        return self._statuses


def test_clients_command_prints_the_table(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    statuses = [
        ClientStatus("claude", "Claude Code", True, "1.2.3", True, True),
        ClientStatus(
            "codex", "OpenAI Codex CLI", False, None, True, False, "client.resume_hint.codex"
        ),
    ]
    monkeypatch.setattr(app, "build_list_clients", lambda: _FakeListClients(statuses))
    assert app.main(["clients"]) == 0
    out = capsys.readouterr().out
    assert "Claude Code" in out
    assert "1.2.3" in out
    assert "(default)" in out  # the default marker on claude
    assert "not installed" in out  # codex absent
    # A qualified yes carries its condition on the row; an unconditional one stays bare.
    assert "resume: yes (once its id is bound, after the first turn)" in out
    assert "resume: yes  (default)" in out  # claude's, unqualified


def test_clients_command_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    statuses = [ClientStatus("claude", "Claude Code", True, "1.2.3", True, True)]
    monkeypatch.setattr(app, "build_list_clients", lambda: _FakeListClients(statuses))
    assert app.main(["clients", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["name"] == "claude"
    assert payload[0]["version"] == "1.2.3"
    assert payload[0]["is_default"] is True


def test_build_list_clients_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_clients(), ListClientsUseCase)


def test_jobs_command_json_empty_is_an_empty_array(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListJobsUseCase):
        def execute(self) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: FakeUseCase())
    assert app.main(["jobs", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []  # not the "No jobs yet" hint


def test_build_list_jobs_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_jobs(), ListJobsUseCase)


def test_format_sessions_empty() -> None:
    assert "No sessions" in app.format_sessions("JOB-1", [])


def test_format_sessions_lists_each() -> None:
    text = app.format_sessions(
        "JOB-1",
        [
            SessionSummary(
                "JOB-1_001",
                "claude",
                cwd="/work/a",
                resumable=True,
                created_at="2026-07-24 09:00:00",
            )
        ],
    )
    assert "JOB-1 — 1 session(s):" in text
    assert "JOB-1_001" in text
    assert "claude" in text
    assert "/work/a" in text  # folder
    assert "2026-07-24 09:00" in text  # date, trimmed to the minute
    assert "yes" in text  # resumable


def test_format_sessions_shows_folder_fallback_and_not_resumable() -> None:
    text = app.format_sessions(
        "JOB-1", [SessionSummary("JOB-1_002", "codex", cwd=None, resumable=False)]
    )
    assert "(folder unknown)" in text  # no stored folder
    assert "no" in text  # not resumable


def test_sessions_command_prints_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListSessionsUseCase):
        def execute(self, job: str) -> list[SessionSummary]:
            return [SessionSummary("JOB-1_001", "claude")]

    monkeypatch.setattr(app, "build_list_sessions", lambda: FakeUseCase())
    assert app.main(["sessions", "JOB-1"]) == 0
    assert "JOB-1_001" in capsys.readouterr().out


def test_sessions_command_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListSessionsUseCase):
        def execute(self, job: str) -> list[SessionSummary]:
            return [SessionSummary("JOB-1_001", "claude")]

    monkeypatch.setattr(app, "build_list_sessions", lambda: FakeUseCase())
    assert app.main(["sessions", "JOB-1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [
        {
            "session_id": "JOB-1_001",
            "client": "claude",
            "cwd": None,
            "resumable": True,
            "created_at": None,
            "turn_count": 0,
            "cost_usd": 0.0,
        }
    ]


def test_build_list_sessions_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_sessions(), ListSessionsUseCase)


def _report() -> UsageReport:
    return UsageReport(
        "JOB-1",
        turns=(
            TurnRow(0.0, "claude-opus-4-8", 2.4, 2714, 4, 35813, "msg_1"),
            TurnRow(0.0, "claude-sonnet-5", 0.5, 2, 7, 100, "msg_2"),
        ),
        models=(
            ModelTotal("claude-opus-4-8", 1, 2714, 4, 35813, 2.4),
            ModelTotal("claude-sonnet-5", 1, 2, 7, 100, 0.5),
        ),
        session_costs=(SessionCost("JOB-1_001", 0.99),),
        turn_count=2,
        input_tokens=2716,
        output_tokens=11,
        cache_tokens=35913,
        duration_s=2.9,
        total_usd=0.99,
    )


def test_format_usage_empty() -> None:
    assert "No usage recorded" in app.format_usage(UsageReport("JOB-1"))


def test_format_usage_renders_turns_models_costs_and_total() -> None:
    text = app.format_usage(_report())
    assert "JOB-1 — usage  (2 turn(s))" in text
    assert "claude-opus-4-8" in text
    assert "[msg_1]" in text  # per-turn id
    assert "2714(+35813 cache)+4 tok" in text  # a turn row's tokens
    assert "── totals by model ──" in text
    assert "1 call(s)" in text
    assert "── cost by session ──" in text
    assert "JOB-1_001  $0.99" in text
    assert "── total ──  2 turn(s)" in text
    assert "$0.99" in text


def test_format_usage_unmetered_timestamp_shows_dashes() -> None:
    assert "--:--:--" in app.format_usage(_report())  # timestamp 0.0 → placeholder


def test_export_command_prints_the_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ExportUsageUseCase):
        def execute(self, job: str) -> UsageReport:
            return _report()

    monkeypatch.setattr(app, "build_export_usage", lambda: FakeUseCase())
    assert app.main(["export", "JOB-1"]) == 0
    out = capsys.readouterr().out
    assert "JOB-1_001" in out
    assert "$0.99" in out


def test_export_command_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ExportUsageUseCase):
        def execute(self, job: str) -> UsageReport:
            return _report()

    monkeypatch.setattr(app, "build_export_usage", lambda: FakeUseCase())
    assert app.main(["export", "JOB-1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["job"] == "JOB-1"
    assert payload["turn_count"] == 2
    assert payload["total_usd"] == 0.99
    assert payload["turns"][0]["model"] == "claude-opus-4-8"
    assert payload["turns"][0]["turn_id"] == "msg_1"
    assert payload["session_costs"] == [{"session_id": "JOB-1_001", "cost_usd": 0.99}]


def test_build_export_usage_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_export_usage(), ExportUsageUseCase)


def test_statusline_command_reads_stdin_and_prints(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, str | None] = {}

    class FakeUseCase(RenderStatuslineUseCase):
        def execute(self, payload_json: str) -> str:
            seen["payload"] = payload_json
            return "Opus 4.8  ·  $0.43"

    def _build_statusline(*_: object) -> FakeUseCase:
        return FakeUseCase()

    monkeypatch.setattr(app, "build_render_statusline", _build_statusline)
    monkeypatch.setattr(app.sys, "stdin", io.StringIO('{"cost": {"total_cost_usd": 0.43}}'))

    assert app.main(["statusline"]) == 0
    # Only the payload crosses this boundary. Which run it belongs to is read by the use
    # case from what the launch announced, not handed over by whoever invoked the command.
    assert '"total_cost_usd": 0.43' in (seen["payload"] or "")
    assert "$0.43" in capsys.readouterr().out


def test_build_render_statusline_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_render_statusline(), RenderStatuslineUseCase)


def test_statusline_renders_the_cursor_plan_block_end_to_end(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    paths.cursor_plan.parent.mkdir(parents=True, exist_ok=True)
    paths.cursor_plan.write_text('{"auto_pct": 6, "api_pct": 3}', encoding="utf-8")
    monkeypatch.setenv("GMLW_CLIENT", "cursor")
    monkeypatch.setattr(app.sys, "stdin", io.StringIO('{"model": {"display_name": "Composer"}}'))
    assert app.main(["statusline"]) == 0  # real cursor parser + renderer
    assert "plan auto 6% · api 3%" in capsys.readouterr().out


def test_main_self_initializes_on_a_real_command(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(calls))

    class _Jobs(ListJobsUseCase):
        def execute(self) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())
    assert app.main(["jobs"]) == 0
    assert calls == ["init"]


def test_main_skips_self_init_for_statusline(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(calls))

    class _Status(RenderStatuslineUseCase):
        def execute(self, payload_json: str) -> str:
            return ""

    def _build_status(*_: object) -> _Status:
        return _Status()

    monkeypatch.setattr(app, "build_render_statusline", _build_status)
    monkeypatch.setattr(app.sys, "stdin", io.StringIO(""))
    assert app.main(["statusline"]) == 0
    assert calls == []


class _FakeInit(InitUseCase):
    def __init__(self, outcome: InitOutcome, calls: list[str]) -> None:
        self._outcome = outcome
        self._calls = calls

    def execute(self) -> InitOutcome:
        self._calls.append("init")
        return self._outcome


def _fresh_outcome(
    *,
    client: str | None = "cursor",
    found: list[str] | None = None,
    persona: str | None = None,
    fresh: bool = True,
    overwrites: tuple[str, ...] = (),
) -> InitOutcome:
    return InitOutcome(
        language="en",
        name="Ada",
        role=AxisSelection("default", "Default", "Default"),
        environment=AxisSelection("work", "Work", "Work"),
        persona=persona,
        client=client,
        found=found if found is not None else (["cursor"] if client else []),
        fresh=fresh,
        overwrites=overwrites,
    )


def _stub_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Jobs(ListJobsUseCase):
        def execute(self) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())


def test_gate_forces_init_when_uninitialised(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    boot: list[str] = []
    ran: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(boot))
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(_fresh_outcome(), ran))
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    assert ran == ["init"]  # forced init ran before the requested command
    assert boot == []  # bootstrap did not (init seeds the layout)
    err = capsys.readouterr().err
    assert "speaking en, calling you Ada" in err
    assert "default client 'cursor'" in err


def test_init_announcement_speaks_the_chosen_language_not_the_os_locale(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression: a French OS locale seeds the startup active localiser, but the user
    # chose English in init. The closing narration must speak the CHOSEN language, not $LANG.
    monkeypatch.setattr(app, "build_localizer", lambda: load_localizer("fr"))  # $LANG=fr seed
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(_fresh_outcome(), []))  # chose en
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    err = capsys.readouterr().err
    assert "set up — speaking en" in err  # English announcement, per the chosen language
    assert "configuré" not in err  # NOT the French ($LANG) announcement
    assert app.i18n.active().lang == "en"  # active re-seeded to the chosen language


def test_gate_skips_init_when_initialised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boot: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(boot))
    monkeypatch.setattr(toml_config_reader, "init_version", _init_done)
    monkeypatch.setattr(app, "build_init", lambda: pytest.fail("init must not run"))
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    assert boot == ["init"]  # only bootstrap ran


def test_init_command_runs_the_use_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ran: list[str] = []
    monkeypatch.setattr(toml_config_reader, "init_version", _init_done)  # even when already done
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(_fresh_outcome(), ran))
    assert app.main(["init"]) == 0
    assert ran == ["init"]


def test_init_command_on_a_fresh_install_never_bootstraps_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `gmlw init` on an un-initialised install must NOT run bootstrap ahead of itself —
    # a pre-seeded config would make init take the legacy (marker-only) path by mistake.
    boot: list[str] = []
    ran: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(boot))
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)  # fresh
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(_fresh_outcome(), ran))
    assert app.main(["init"]) == 0
    assert ran == ["init"]  # init ran exactly once
    assert boot == []  # bootstrap never ran


def test_init_announces_no_client_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)
    monkeypatch.setattr(
        app, "build_init", lambda: _FakeInit(_fresh_outcome(client=None, found=[]), [])
    )
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    assert "no supported client found on your PATH" in capsys.readouterr().err


def test_init_on_legacy_reports_the_merge_and_any_overwrites(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)
    outcome = _fresh_outcome(fresh=False, overwrites=("client.default: cursor → claude",))
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(outcome, []))
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    err = capsys.readouterr().err
    assert "your choices were saved into" in err
    assert "client.default: cursor → claude" in err  # the replaced value is surfaced


def test_build_init_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_init(), InitUseCase)


def test_init_announces_the_chosen_persona(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(_fresh_outcome(persona="butler"), []))
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    assert "persona 'butler' selected" in capsys.readouterr().err


def test_migration_is_announced_on_the_bootstrap_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # An already-initialised install (bootstrap path) still runs migration — catching an
    # install initialised before migration existed.
    report = MigrationReport(environment="work", moved=["stack.md", "policies.md"])
    monkeypatch.setattr(app, "build_migrate_layout", lambda: _FakeMigrate(report))
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    err = capsys.readouterr().err
    assert "migrated 2 item(s) from profile/company into environments/work" in err
    assert "stack.md" in err


def test_migration_surfaces_skipped_collisions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = MigrationReport(environment="work", moved=["ok.md"], skipped=["stack.md"])
    monkeypatch.setattr(app, "build_migrate_layout", lambda: _FakeMigrate(report))
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    err = capsys.readouterr().err
    assert "left 1 item(s) in profile/company" in err
    assert "stack.md" in err


def test_no_migration_output_when_nothing_moved(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_jobs(monkeypatch)  # fixture's migrate stub returns an empty report
    assert app.main(["jobs"]) == 0
    assert "migrated" not in capsys.readouterr().err


def test_init_command_runs_migration_after_init(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(toml_config_reader, "init_version", _init_absent)
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(_fresh_outcome(), []))
    report = MigrationReport(environment="work", moved=["co.md"])
    monkeypatch.setattr(app, "build_migrate_layout", lambda: _FakeMigrate(report))
    assert app.main(["init"]) == 0
    err = capsys.readouterr().err
    assert "set up — speaking en" in err  # init announced
    assert "migrated 1 item(s)" in err  # and migration ran after it


def test_build_migrate_layout_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_migrate_layout(), MigrateLayoutUseCase)


def test_start_does_not_print_the_greeting_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The host greeting is now injected into the session context (rendered in-band by the
    # client), not printed to the launch-time stderr that the client immediately clears.
    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["start", "JOB-1"]) == 0
    assert "# Greeting" not in capsys.readouterr().err  # no greeting on stderr anymore


def test_build_render_greeting_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_render_greeting(), RenderGreetingUseCase)


def _not_ready(client: str, installed: tuple[str, ...] = ()) -> ClientReadiness:
    """A not-ready verdict shaped the way the use case now builds one.

    The install commands are resolved by the use case, not by whoever renders them, so a
    fake that omitted them would let the guidance print ``None`` and the test still pass.
    """
    catalogue = TomlClientCatalogAdapter().supported()
    system = platform.system()
    return ClientReadiness(
        client=client,
        ready=False,
        missing=_client(client),
        installed=installed,
        install_command=_client(client).install_for(system),
        catalogue_install_commands=tuple((e.name, e.install_for(system)) for e in catalogue),
    )


def test_start_aborts_with_guidance_when_client_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    launched: list[str] = []

    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            launched.append(command.job)
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    readiness = _not_ready("cursor")
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient(readiness))

    assert app.main(["start", "JOB-1", "--client", "cursor"]) == 2
    err = capsys.readouterr().err
    assert "cursor.com/install" in err  # the install command
    assert "cursor-agent login" in err  # the login hint
    assert launched == []  # never launched


def test_start_missing_client_suggests_an_installed_alternative(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_start_job", lambda: None)
    readiness = _not_ready("claude", installed=("codex",))
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient(readiness))
    assert app.main(["start", "JOB-1"]) == 2
    assert "--client codex" in capsys.readouterr().err  # suggest the one they have


def test_start_lists_all_when_no_client_installed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_start_job", lambda: None)
    readiness = _not_ready("claude")
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient(readiness))
    assert app.main(["start", "JOB-1"]) == 2
    err = capsys.readouterr().err
    for (
        info
    ) in TomlClientCatalogAdapter().supported():  # every supported client's install is offered
        assert info.install_for(platform.system()) in err


def test_workflow_new_aborts_when_client_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_new_workflow", lambda: None)
    readiness = _not_ready("codex")
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient(readiness))
    assert app.main(["workflow", "new", "doc-review", "--client", "codex"]) == 2
    assert _client("codex").install_for(platform.system()) in capsys.readouterr().err


def test_build_check_client_ready_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_check_client_ready(), CheckClientReadyUseCase)


def test_start_aborts_cleanly_when_the_cwd_is_deleted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _CurrentGone(CheckLaunchLocationUseCase):
        def execute(self, session_folder: str | None = None) -> LaunchLocation:
            return LaunchLocation(LaunchLocationProblem.CURRENT_GONE)

    monkeypatch.setattr(app, "build_check_launch_location", lambda: _CurrentGone())
    monkeypatch.setattr(app, "build_start_job", lambda: None)  # must never be reached
    assert app.main(["start", "JOB-1"]) == 2
    assert "current directory no longer exists" in capsys.readouterr().err


def test_creds_set_reads_stdin_and_stores_without_echoing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, SetCredentialCommand] = {}

    class FakeUseCase(SetCredentialUseCase):
        def execute(self, command: SetCredentialCommand) -> None:
            seen["command"] = command

    monkeypatch.setattr(app, "build_set_credential", lambda: FakeUseCase())
    monkeypatch.setattr(app.sys, "stdin", io.StringIO("ghp_secret\n"))

    assert app.main(["creds", "set", "doc-review", "GITHUB_TOKEN"]) == 0
    # The command names what to store, not the secret: reading it is an outward reach, so
    # the use case does it. How it is read without echoing is asserted against that prompt.
    assert seen["command"] == SetCredentialCommand("doc-review", "GITHUB_TOKEN")
    out = capsys.readouterr().out
    assert "stored doc-review.GITHUB_TOKEN" in out
    assert "ghp_secret" not in out  # the secret is never echoed


def test_build_set_credential_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_set_credential(), SetCredentialUseCase)


def test_incomplete_subcommand_prints_its_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["workflow"]) == 0  # no action -> auto help
    out = capsys.readouterr().out
    assert "usage: gmlw workflow" in out
    assert "new" in out
    assert "list" in out


def test_incomplete_persona_and_plugins_print_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["persona"]) == 0
    assert "usage: gmlw persona" in capsys.readouterr().out
    assert app.main(["plugins"]) == 0
    assert "usage: gmlw plugins" in capsys.readouterr().out


def test_complete_subcommand_does_not_print_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _Workflows(ListWorkflowsUseCase):
        def execute(self) -> list[str]:
            return []

    monkeypatch.setattr(app, "build_list_workflows", lambda: _Workflows())
    assert app.main(["workflow", "list"]) == 0
    assert "usage: gmlw workflow" not in capsys.readouterr().out  # it ran, not helped


def _deploying_use_case(seen: dict[str, NewWorkflowCommand]) -> NewWorkflowUseCase:
    class FakeUseCase(NewWorkflowUseCase):
        def execute(self, command: NewWorkflowCommand) -> NewWorkflowResult:
            seen["command"] = command
            return NewWorkflowResult(
                exit_code=0,
                outcome=WorkflowOutcome.DEPLOYED,
                name=command.label or "nightly-etl",
                draft_path="/drafts/create-workflow_001",
            )

    return FakeUseCase()


def test_workflow_new_dispatches_to_the_use_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, NewWorkflowCommand] = {}
    monkeypatch.setattr(app, "build_new_workflow", lambda: _deploying_use_case(seen))
    assert app.main(["workflow", "new", "doc-review"]) == 0
    assert seen["command"] == NewWorkflowCommand(label="doc-review", client="claude")
    assert "created" in capsys.readouterr().err  # the deployed announcement


def test_workflow_new_without_a_name_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, NewWorkflowCommand] = {}
    monkeypatch.setattr(app, "build_new_workflow", lambda: _deploying_use_case(seen))
    assert app.main(["workflow", "new"]) == 0
    assert seen["command"] == NewWorkflowCommand(label=None, client="claude")  # name optional


def test_workflow_new_reports_a_seed_name_collision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(NewWorkflowUseCase):
        def execute(self, command: NewWorkflowCommand) -> NewWorkflowResult:
            raise WorkflowExistsError("workflow already exists: 'doc-review'")

    monkeypatch.setattr(app, "build_new_workflow", lambda: FailingUseCase())
    assert app.main(["workflow", "new", "doc-review"]) == 2
    err = capsys.readouterr().err
    assert "already exists" in err
    assert "gmlw workflow edit doc-review" in err  # points at editing the existing one


def test_workflow_new_reports_an_incomplete_draft(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class IncompleteUseCase(NewWorkflowUseCase):
        def execute(self, command: NewWorkflowCommand) -> NewWorkflowResult:
            return NewWorkflowResult(
                exit_code=0,
                outcome=WorkflowOutcome.INCOMPLETE,
                name=None,
                draft_path="/drafts/create-workflow_002",
            )

    monkeypatch.setattr(app, "build_new_workflow", lambda: IncompleteUseCase())
    assert app.main(["workflow", "new"]) == 0
    err = capsys.readouterr().err
    assert "wasn't finished" in err
    assert "/drafts/create-workflow_002" in err  # the kept draft is surfaced


def test_workflow_new_guided_flag_sets_guided(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, NewWorkflowCommand] = {}
    monkeypatch.setattr(app, "build_new_workflow", lambda: _deploying_use_case(seen))
    assert app.main(["workflow", "new", "--guided"]) == 0
    assert seen["command"].guided is True


def test_workflow_new_quick_flag_unsets_guided(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, NewWorkflowCommand] = {}
    monkeypatch.setattr(app, "build_new_workflow", lambda: _deploying_use_case(seen))
    assert app.main(["workflow", "new", "--quick"]) == 0
    assert seen["command"].guided is False


def test_workflow_new_off_a_tty_defaults_to_quick(monkeypatch: pytest.MonkeyPatch) -> None:
    # No flag + no terminal (tests) -> the guided chooser declines -> lean interview.
    seen: dict[str, NewWorkflowCommand] = {}
    monkeypatch.setattr(app, "build_new_workflow", lambda: _deploying_use_case(seen))
    assert app.main(["workflow", "new"]) == 0
    assert seen["command"].guided is False


def test_workflow_new_guided_and_quick_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):  # argparse rejects both at once
        app.build_parser().parse_args(["workflow", "new", "--guided", "--quick"])


def test_build_new_workflow_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_new_workflow(), NewWorkflowUseCase)


def test_format_workflows_empty() -> None:
    assert "No workflows yet" in app.format_workflows([])


def test_format_workflows_lists_each() -> None:
    text = app.format_workflows(
        [
            Workflow("doc-review", "Doc review", "Reviews a document."),
            Workflow("release", "release", ""),  # no sidecar: label is the slug
        ]
    )
    assert "2 workflow(s):" in text
    assert "doc-review" in text
    assert "Doc review" in text
    assert "release" in text
    # A workflow with no sidecar must not print its slug twice.
    assert text.count("release") == 1


def test_workflow_list_prints_the_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListWorkflowCatalogUseCase):
        def execute(self) -> list[Workflow]:
            return [Workflow("doc-review", "Doc review", "Reviews a document.")]

    monkeypatch.setattr(app, "build_list_workflow_catalog", lambda: FakeUseCase())
    assert app.main(["workflow", "list"]) == 0
    out = capsys.readouterr().out
    assert "doc-review" in out  # the slug the user types
    assert "Doc review" in out  # and the words its author gave it
    assert "Reviews a document." in out


def test_workflow_list_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListWorkflowCatalogUseCase):
        def execute(self) -> list[Workflow]:
            return [Workflow("doc-review", "Doc review", "Reviews a document.")]

    monkeypatch.setattr(app, "build_list_workflow_catalog", lambda: FakeUseCase())
    assert app.main(["workflow", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [
        {"slug": "doc-review", "label": "Doc review", "description": "Reviews a document."}
    ]


def test_build_list_workflows_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_workflows(), ListWorkflowsUseCase)


def test_format_personas_lists_name_and_description() -> None:
    text = app.format_personas(
        [Persona("butler", "A Jeeves.", "g", "b"), Persona("plain", "Neutral.", "g", "b")]
    )
    assert "2 persona(s)" in text
    assert "butler" in text
    assert "A Jeeves." in text


def test_persona_list_prints_the_personas(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListPersonasUseCase):
        def execute(self) -> list[Persona]:
            return [Persona("butler", "A Jeeves.", "g", "b")]

    monkeypatch.setattr(app, "build_list_personas", lambda: FakeUseCase())
    assert app.main(["persona", "list"]) == 0
    out = capsys.readouterr().out
    assert "butler" in out
    assert "A Jeeves." in out


def test_persona_list_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListPersonasUseCase):
        def execute(self) -> list[Persona]:
            return [Persona("butler", "A Jeeves.", "g", "b")]

    monkeypatch.setattr(app, "build_list_personas", lambda: FakeUseCase())
    assert app.main(["persona", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"name": "butler", "description": "A Jeeves."}]


def test_build_list_personas_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_personas(), ListPersonasUseCase)


def test_plugins_list_prints_the_plugins(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListPluginsUseCase):
        def execute(self) -> list[Plugin]:
            return [Plugin("cursor-mitm", "Cursor via MITM proxy")]

    monkeypatch.setattr(app, "build_list_plugins", lambda: FakeUseCase())
    assert app.main(["plugins", "list"]) == 0
    out = capsys.readouterr().out
    assert "cursor-mitm" in out
    assert "Cursor via MITM proxy" in out


def test_plugins_list_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListPluginsUseCase):
        def execute(self) -> list[Plugin]:
            return [Plugin("cursor-mitm", "MITM")]

    monkeypatch.setattr(app, "build_list_plugins", lambda: FakeUseCase())
    assert app.main(["plugins", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"id": "cursor-mitm", "description": "MITM"}]


def test_plugins_list_empty_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListPluginsUseCase):
        def execute(self) -> list[Plugin]:
            return []

    monkeypatch.setattr(app, "build_list_plugins", lambda: FakeUseCase())
    assert app.main(["plugins", "list"]) == 0
    assert "~/.gmlw/plugins/" in capsys.readouterr().out


def test_build_list_plugins_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_plugins(), ListPluginsUseCase)


class _NoBootstrap(BootstrapUseCase):
    def execute(self) -> None:
        """Skip real ~/.gmlw seeding in a CLI validation test."""


def test_start_rejects_an_unsafe_job_id(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["start", "../etc/passwd"]) == 2
    assert "invalid job id" in capsys.readouterr().err


def test_sessions_rejects_an_unsafe_job_id(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["sessions", "a/b"]) == 2
    assert "invalid job id" in capsys.readouterr().err


def test_start_aborts_on_unreadable_settings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            raise ClientSettingsUnusableError("/x/.claude/settings.json")

    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    monkeypatch.setattr(app, "build_start_job", lambda: FailingUseCase())
    assert app.main(["start", "JOB-1"]) == 2
    assert "is not valid JSON" in capsys.readouterr().err


def test_creds_set_rejects_invalid_workflow_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["creds", "set", "Bad Name", "TOKEN"]) == 2
    assert "invalid workflow name" in capsys.readouterr().err


def test_creds_set_rejects_invalid_env_var_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["creds", "set", "wf", "1BAD"]) == 2
    assert "invalid environment-variable name" in capsys.readouterr().err


def test_config_list_prints_settings_with_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["config", "list"]) == 0
    out = capsys.readouterr().out
    assert "client.default" in out
    assert "profile.default_role" in out


def test_config_list_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["config", "list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    keys = {row["key"] for row in payload}
    assert "logging.level" in keys


def test_config_get_prints_one_setting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["config", "get", "logging.level"]) == 0
    out = capsys.readouterr().out
    assert "logging.level = warning" in out
    assert "allowed:" in out


def test_config_get_unknown_key_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["config", "get", "nope.key"]) == 2
    assert "unknown setting" in capsys.readouterr().err


def test_config_set_persists_and_echoes_the_change(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["config", "set", "profile.default_role", "reviewer"]) == 0
    out = capsys.readouterr().out
    assert "profile.default_role = reviewer" in out
    assert 'default_role = "reviewer"' in (paths.home / "config.toml").read_text(encoding="utf-8")


def test_config_set_invalid_value_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["config", "set", "logging.level", "loud"]) == 2
    assert "invalid value" in capsys.readouterr().err


def test_bare_config_shows_its_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["config"]) == 0
    assert "list" in capsys.readouterr().out  # the sub-action help


def test_build_config_commands_is_wired() -> None:
    assert isinstance(composition.build_config_commands(), ConfigCommandsUseCase)


def test_exit_receipt_prints_cost_and_next_steps(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            return StartJobResult(exit_code=0, job=command.job, session_id="JOB-1_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["start", "JOB-1"]) == 0
    err = capsys.readouterr().err
    assert "JOB-1_001" in err  # this session
    assert "gmlw start JOB-1 --resume-latest" in err  # resume command
    assert "gmlw export JOB-1" in err  # report command


def test_exit_receipt_tip_is_shown_once_then_suppressed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            return StartJobResult(exit_code=0, job=command.job, session_id="JOB-1_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["start", "JOB-1"]) == 0
    first = capsys.readouterr().err
    assert "tip:" in first  # the first unseen hint
    # a second run shows a different hint (the first was recorded as seen)
    assert app.main(["start", "JOB-1"]) == 0
    second = capsys.readouterr().err
    assert "tip:" in second
    assert first != second


def test_exit_receipt_tip_suppressed_when_hints_disabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (paths.home).mkdir(parents=True, exist_ok=True)
    (paths.home / "config.toml").write_text("[hints]\nshow = false\n", encoding="utf-8")

    class FakeUseCase(StartJobUseCase):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            return StartJobResult(exit_code=0, job=command.job, session_id="JOB-1_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["start", "JOB-1"]) == 0
    assert "tip:" not in capsys.readouterr().err


def test_workflow_edit_dispatches_to_the_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, EditWorkflowCommand] = {}

    class FakeUseCase(EditWorkflowUseCase):
        def execute(self, command: EditWorkflowCommand) -> int:
            seen["command"] = command
            return 0

    monkeypatch.setattr(app, "build_edit_workflow", lambda: FakeUseCase())
    assert app.main(["workflow", "edit", "doc-review"]) == 0
    assert seen["command"] == EditWorkflowCommand(name="doc-review", client="claude")


def test_workflow_edit_reports_a_missing_workflow(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(EditWorkflowUseCase):
        def execute(self, command: EditWorkflowCommand) -> int:
            raise WorkflowNotFoundError("unknown workflow: 'missing'")

    monkeypatch.setattr(app, "build_edit_workflow", lambda: FailingUseCase())
    assert app.main(["workflow", "edit", "missing"]) == 2
    assert "unknown workflow" in capsys.readouterr().out


def test_build_edit_workflow_is_wired() -> None:
    assert isinstance(composition.build_edit_workflow(), EditWorkflowUseCase)


class _FakeCreateAxis(CreateAxisUseCase):
    def __init__(self, error: Exception | None = None) -> None:
        self.seen: CreateAxisCommand | None = None
        self._error = error

    def execute(self, command: CreateAxisCommand) -> CreateAxisResult:
        self.seen = command
        if self._error is not None:
            raise self._error
        return CreateAxisResult(
            kind=command.kind,
            slug="client-project",
            label=command.label,
            made_default=command.make_default,
        )


def test_environment_new_builds_the_command_and_confirms(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeCreateAxis()
    monkeypatch.setattr(app, "build_create_axis", lambda: fake)
    assert app.main(["environment", "new", "Client Project", "--default"]) == 0
    assert fake.seen == CreateAxisCommand(
        kind=AxisKind.ENVIRONMENT, label="Client Project", description="", make_default=True
    )
    out = capsys.readouterr().out
    assert "client-project" in out  # the derived slug
    assert "default" in out  # made-default line printed


def test_role_new_defaults_description_empty_and_no_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeCreateAxis()
    monkeypatch.setattr(app, "build_create_axis", lambda: fake)
    assert app.main(["role", "new", "Code Reviewer"]) == 0
    assert fake.seen is not None
    assert fake.seen.kind == AxisKind.ROLE
    assert fake.seen.make_default is False


def test_environment_new_reports_a_collision_and_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeCreateAxis(error=AxisExistsError("environment already exists: 'work'"))
    monkeypatch.setattr(app, "build_create_axis", lambda: fake)
    assert app.main(["environment", "new", "Work"]) == 2
    assert "already exists" in capsys.readouterr().err


def test_build_create_axis_is_wired() -> None:
    assert isinstance(composition.build_create_axis(), CreateAxisUseCase)


def test_preflight_resume_cwd_passes_when_the_folder_has_no_stored_cwd() -> None:
    # A pre-folder session (cwd None) resumes in the current directory; nothing to guard.
    assert app._preflight_resume_cwd(None) is True


def test_preflight_resume_cwd_passes_when_the_folder_exists(tmp_path: Path) -> None:
    assert app._preflight_resume_cwd(str(tmp_path)) is True


def test_preflight_resume_cwd_blocks_and_names_a_deleted_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gone = tmp_path / "was-here"
    assert app._preflight_resume_cwd(str(gone)) is False
    err = capsys.readouterr().err
    assert str(gone) in err  # the missing folder is named plainly
    assert "Traceback" not in err


class _Tty(io.StringIO):
    """A stdin/stdout stand-in that claims to be a terminal, so ``_tui`` builds the menu."""

    def isatty(self) -> bool:
        return True


def test_tui_reads_the_default_client_after_the_menu_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A default-client switch made *inside* the menu must apply to the launch that follows it,
    # not only to the next run of gmlw: the client is resolved after run() returns, not before.
    monkeypatch.setattr(app.sys, "stdin", _Tty())
    monkeypatch.setattr(app.sys, "stdout", _Tty())

    class _MenuSwitchingTheClient:
        def __init__(self, _jobs: object, **kwargs: object) -> None:
            self.opened_with = kwargs["current_client"]

        def run(self) -> tui.MenuChoice:  # the user switches the default, then starts a job
            path = toml_config_reader.config_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[client]\ndefault = "codex"\n', encoding="utf-8")
            return tui.MenuChoice(action="start", job="alpha")

    monkeypatch.setattr(tui, "MenuApp", _MenuSwitchingTheClient)
    launched: list[str] = []

    def _record_launch(
        _job: str, _resume: bool, _session: str | None, _cwd: str | None, client: str
    ) -> int:
        launched.append(client)
        return 0

    monkeypatch.setattr(app, "_tui_launch_job", _record_launch)
    assert app._tui() == 0
    assert launched == ["codex"]  # the switch just made, not the default the menu opened on


# --------------------------------------------------------------------------- #
# Deleting jobs and sessions                                                   #
# --------------------------------------------------------------------------- #


class _FakeDeleteJobs(DeleteJobsUseCase):
    """Records what it was asked to preview and delete; deletes nothing."""

    def __init__(
        self,
        footprints: list[JobFootprint],
        error: Exception | None = None,
        outcome: list[JobFootprint] | None = None,
    ) -> None:
        self._footprints = footprints
        self._error = error
        #: What the delete reports afterwards, when that differs from what it previewed --
        #: a job whose files would not go comes back marked.
        self._outcome = outcome
        self.previewed: list[list[str]] = []
        self.executed: list[list[str]] = []

    def preview(self, jobs: Sequence[str]) -> list[JobFootprint]:
        if self._error is not None:
            raise self._error
        self.previewed.append(list(jobs))
        return self._footprints

    def execute(self, jobs: Sequence[str]) -> list[JobFootprint]:
        self.executed.append(list(jobs))
        return self._outcome if self._outcome is not None else self._footprints


class _FakeDeleteSessions(DeleteSessionsUseCase):
    """Records what it was asked to preview and delete; deletes nothing."""

    def __init__(
        self,
        footprints: list[SessionFootprint],
        error: Exception | None = None,
        outcome: list[SessionFootprint] | None = None,
    ) -> None:
        self._footprints = footprints
        self._error = error
        self._outcome = outcome
        self.executed: list[tuple[str, list[str]]] = []

    def preview(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        if self._error is not None:
            raise self._error
        return self._footprints

    def execute(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        self.executed.append((job, list(sessions)))
        return self._outcome if self._outcome is not None else self._footprints


def _job_footprint(job: str = "alpha") -> JobFootprint:
    return JobFootprint(
        job=job, sessions=3, turns=41, cost_usd=1.25, contexts=3, transcript_calls=6
    )


def _session_footprint(session: str = "alpha_002") -> SessionFootprint:
    return SessionFootprint(
        job="alpha", session=session, turns=0, cost_usd=0.0, contexts=1, transcript_calls=0
    )


class _TtyStderr:
    """Whatever stderr currently is, claiming to be a terminal.

    Not a plain :class:`_Tty`: the confirmation prompt only appears when *stderr* is a
    terminal, and swapping capsys's stream out for a private buffer would take the very
    output the test is checking with it. This delegates the writes and lies only about
    ``isatty``.
    """

    def __init__(self, stream: object) -> None:
        self._stream = stream

    def write(self, text: str) -> int:
        return int(self._stream.write(text))  # type: ignore[attr-defined]  # any text stream

    def flush(self) -> None:
        self._stream.flush()  # type: ignore[attr-defined]  # any text stream

    def isatty(self) -> bool:
        return True


def _answer(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    """Make the confirmation prompt reachable, and answer it with ``reply``."""
    monkeypatch.setattr(app.sys, "stdin", _Tty())
    monkeypatch.setattr(app.sys, "stderr", _TtyStderr(app.sys.stderr))
    monkeypatch.setattr("builtins.input", lambda _prompt="": reply)


def test_bare_jobs_and_sessions_still_list() -> None:
    """The delete sub-action is optional — the list commands are unchanged."""
    parser = app.build_parser()
    assert parser.parse_args(["jobs"]).jobs_command is None
    assert parser.parse_args(["jobs", "--json"]).json is True
    assert parser.parse_args(["sessions", "alpha"]).sessions_command is None
    assert parser.parse_args(["sessions", "alpha", "--json"]).json is True


def test_parser_parses_both_delete_forms() -> None:
    parser = app.build_parser()
    jobs = parser.parse_args(["jobs", "delete", "alpha", "beta", "--yes"])
    assert (jobs.jobs_command, jobs.job, jobs.yes) == ("delete", ["alpha", "beta"], True)
    sessions = parser.parse_args(["sessions", "alpha", "delete", "alpha_001"])
    assert (sessions.sessions_command, sessions.job, sessions.session, sessions.yes) == (
        "delete",
        "alpha",
        ["alpha_001"],
        False,
    )


def test_jobs_delete_previews_then_deletes_when_confirmed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeDeleteJobs([_job_footprint()])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)
    _answer(monkeypatch, "y")

    assert app.main(["jobs", "delete", "alpha"]) == 0
    assert fake.executed == [["alpha"]]
    err = capsys.readouterr().err
    assert "3 session(s)" in err  # the footprint was shown before the question
    assert "41 turn(s)" in err


def test_jobs_delete_declined_removes_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeDeleteJobs([_job_footprint()])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)
    _answer(monkeypatch, "n")

    assert app.main(["jobs", "delete", "alpha"]) == 2
    assert fake.executed == []
    assert "nothing was deleted" in capsys.readouterr().err


def test_yes_skips_the_question_entirely(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeDeleteJobs([_job_footprint()])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)

    def _never(_prompt: str = "") -> str:
        raise AssertionError("--yes must not prompt")

    monkeypatch.setattr("builtins.input", _never)
    assert app.main(["jobs", "delete", "alpha", "--yes"]) == 0
    assert fake.executed == [["alpha"]]


def test_off_a_tty_a_delete_is_refused_rather_than_assumed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeDeleteJobs([_job_footprint()])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)
    monkeypatch.setattr(app.sys, "stdin", io.StringIO())  # isatty() is False

    assert app.main(["jobs", "delete", "alpha"]) == 2
    assert fake.executed == []
    assert "--yes" in capsys.readouterr().err  # and says how to mean it


def test_jobs_delete_reports_an_unknown_job_and_stops(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = NoSuchJobError("error.job.not_found", job="nope")
    fake = _FakeDeleteJobs([], error=error)
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)

    assert app.main(["jobs", "delete", "nope", "--yes"]) == 2
    assert fake.executed == []
    assert "nope" in capsys.readouterr().err


def test_repeated_ids_are_asked_for_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeDeleteJobs([_job_footprint()])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)

    assert app.main(["jobs", "delete", "alpha", "beta", "alpha", "--yes"]) == 0
    assert fake.executed == [["alpha", "beta"]]


def test_an_invalid_job_id_never_reaches_the_use_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _unreachable() -> DeleteJobsUseCase:
        raise AssertionError("a bad id must be refused at the boundary")

    monkeypatch.setattr(app, "build_delete_jobs", _unreachable)
    assert app.main(["jobs", "delete", "../etc", "--yes"]) == 2
    assert "invalid job id" in capsys.readouterr().err


def test_sessions_delete_previews_then_deletes_when_confirmed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeDeleteSessions([_session_footprint()])
    monkeypatch.setattr(app, "build_delete_sessions", lambda: fake)
    _answer(monkeypatch, "y")

    assert app.main(["sessions", "alpha", "delete", "alpha_002"]) == 0
    assert fake.executed == [("alpha", ["alpha_002"])]
    assert "alpha_002" in capsys.readouterr().err


def test_sessions_delete_reports_an_unknown_session(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = NoSuchSessionError("error.session.not_found", session="alpha_009", job="alpha")
    fake = _FakeDeleteSessions([], error=error)
    monkeypatch.setattr(app, "build_delete_sessions", lambda: fake)

    assert app.main(["sessions", "alpha", "delete", "alpha_009", "--yes"]) == 2
    assert fake.executed == []
    assert "alpha_009" in capsys.readouterr().err


def test_format_job_footprints_names_every_kind_of_thing_that_goes() -> None:
    text = app.format_job_footprints([_job_footprint(), _job_footprint("throwaway")])
    assert "2 job(s)" in text
    assert "alpha" in text
    assert "throwaway" in text
    assert "context file(s)" in text
    assert "transcript file(s)" in text


def test_format_session_footprints_names_the_job_it_empties() -> None:
    text = app.format_session_footprints("alpha", [_session_footprint()])
    assert "alpha" in text
    assert "alpha_002" in text


def test_format_session_usage_names_an_empty_session() -> None:
    """0 turns reads as a word, not a row of zeroes — it is what a user is scanning for."""
    assert app.format_session_usage(SessionSummary("alpha_001", "claude")) == "empty"


def test_format_session_usage_shows_turns_and_cost() -> None:
    summary = SessionSummary("alpha_002", "claude", turn_count=12, cost_usd=1.5)
    assert app.format_session_usage(summary) == "12 turn(s) $1.50"


def test_format_sessions_marks_the_empty_one() -> None:
    text = app.format_sessions(
        "alpha",
        [
            SessionSummary("alpha_001", "claude"),
            SessionSummary("alpha_002", "claude", turn_count=12, cost_usd=1.5),
        ],
    )
    assert "empty" in text
    assert "12 turn(s)" in text


def test_build_delete_use_cases_are_wired() -> None:
    assert isinstance(composition.build_delete_jobs(), DeleteJobsUseCase)
    assert isinstance(composition.build_delete_sessions(), DeleteSessionsUseCase)


# --------------------------------------------------------------------------- #
# The menu loop: an errand comes back, a launch does not                       #
# --------------------------------------------------------------------------- #


def _menu_returning(*choices: tui.MenuChoice | None) -> list[tui.MenuChoice | None]:
    """A scripted sequence of menu results, one per pass through the loop."""
    return list(choices)


def _drive_tui(
    monkeypatch: pytest.MonkeyPatch, script: list[tui.MenuChoice | None]
) -> tuple[int, int]:
    """Run ``_tui`` with ``_run_menu`` scripted; return (exit code, times the menu opened)."""
    passes = {"n": 0}

    def _fake_menu() -> tui.MenuChoice | None:
        index = passes["n"]
        passes["n"] += 1
        if index >= len(script):
            raise AssertionError("the loop opened the menu more times than the script allows")
        return script[index]

    monkeypatch.setattr(app.sys, "stdin", _Tty())
    monkeypatch.setattr(app.sys, "stdout", _Tty())
    monkeypatch.setattr(app, "_run_menu", _fake_menu)
    monkeypatch.setattr(app, "_pause_before_menu", lambda: None)
    return app._tui(), passes["n"]


def test_quitting_the_menu_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _drive_tui(monkeypatch, _menu_returning(None)) == (0, 1)


def test_config_setup_returns_to_the_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[bool] = []

    def _init() -> int:
        ran.append(True)
        return 0

    monkeypatch.setattr(app, "_run_init", _init)

    code, opened = _drive_tui(monkeypatch, _menu_returning(tui.MenuChoice(action="init"), None))

    assert ran == [True]
    assert (code, opened) == (0, 2)


def test_a_launch_ends_gmlw_rather_than_returning(monkeypatch: pytest.MonkeyPatch) -> None:
    """A client owned the terminal; when it is done, so is gmlw."""

    def _launch(
        _job: str, _resume: bool, _session: str | None, _cwd: str | None, _client: str
    ) -> int:
        return 7

    monkeypatch.setattr(app, "_tui_launch_job", _launch)

    code, opened = _drive_tui(
        monkeypatch, _menu_returning(tui.MenuChoice(action="start", job="alpha"))
    )

    assert (code, opened) == (7, 1)  # the exit code is the client's, and the menu never reopened


def test_a_workflow_run_ends_gmlw(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run(_workflow: str, _client: str) -> int:
        return 3

    monkeypatch.setattr(app, "_run_workflow", _run)

    code, opened = _drive_tui(
        monkeypatch, _menu_returning(tui.MenuChoice(action="run", workflow="nightly"))
    )

    assert (code, opened) == (3, 1)


# --------------------------------------------------------------------------- #
# The Deleter the wiring injects into the menu                                 #
# --------------------------------------------------------------------------- #


def _built_deleter(monkeypatch: pytest.MonkeyPatch) -> tui.Deleter:
    """The Deleter `_run_menu` builds, captured without opening the menu."""
    captured: dict[str, tui.Deleter] = {}

    class _Capture:
        def __init__(self, _jobs: object, **kwargs: object) -> None:
            captured["deleter"] = cast(tui.Deleter, kwargs["deleter"])

        def run(self) -> tui.MenuChoice | None:
            return None

    monkeypatch.setattr(app.sys, "stdin", _Tty())
    monkeypatch.setattr(app.sys, "stdout", _Tty())
    monkeypatch.setattr(tui, "MenuApp", _Capture)
    app._run_menu()
    return captured["deleter"]


def test_the_menu_is_given_a_deleter_that_previews_without_deleting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeDeleteJobs([_job_footprint()])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)

    text = _built_deleter(monkeypatch).preview_jobs(("alpha",))

    assert "3 session(s)" in text  # the footprint the confirm screen shows
    assert fake.executed == []  # a preview removes nothing


def test_the_injected_deleter_removes_jobs_and_reports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeDeleteJobs([_job_footprint()])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)

    message = _built_deleter(monkeypatch).delete_jobs(("alpha",))

    assert fake.executed == [["alpha"]]
    assert "removed" in message


def test_the_injected_deleter_removes_sessions_and_reports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeDeleteSessions([_session_footprint()])
    monkeypatch.setattr(app, "build_delete_sessions", lambda: fake)

    deleter = _built_deleter(monkeypatch)
    preview = deleter.preview_sessions("alpha", ("alpha_002",))
    message = deleter.delete_sessions("alpha", ("alpha_002",))

    assert "alpha_002" in preview
    assert fake.executed == [("alpha", ["alpha_002"])]
    assert "removed" in message


def test_a_stale_selection_is_reported_rather_than_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The menu holds a snapshot; if it went stale the message goes on screen, not a crash."""
    error = NoSuchJobError("error.job.not_found", job="gone")
    monkeypatch.setattr(app, "build_delete_jobs", lambda: _FakeDeleteJobs([], error=error))

    assert "gone" in _built_deleter(monkeypatch).preview_jobs(("gone",))


def test_the_menu_reloads_its_job_list_on_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """What makes a job the user just deleted leave the list they are standing on."""
    captured: dict[str, object] = {}

    class _Capture:
        def __init__(self, _jobs: object, **kwargs: object) -> None:
            captured["reload"] = kwargs["reload_jobs"]

        def run(self) -> tui.MenuChoice | None:
            return None

    class _Jobs(ListJobsUseCase):
        def execute(self) -> list[JobSummary]:
            return [JobSummary(job="beta", session_count=1)]

    monkeypatch.setattr(app.sys, "stdin", _Tty())
    monkeypatch.setattr(app.sys, "stdout", _Tty())
    monkeypatch.setattr(tui, "MenuApp", _Capture)
    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())
    app._run_menu()

    reload_jobs = cast("Callable[[], list[tui.JobChoice]]", captured["reload"])
    assert [j.job for j in reload_jobs()] == ["beta"]


def test_the_in_app_verbs_no_longer_come_back_through_the_choice_handler() -> None:
    """Delete, export and import are done in-app; none should reach the terminal hand-off."""
    for action in ("jobs_delete", "sessions_delete", "workflow_export", "workflow_import"):
        assert app._act_on_tui_choice(tui.MenuChoice(action=action)) == 0


def _built_archiver(monkeypatch: pytest.MonkeyPatch) -> tui.Archiver:
    """The Archiver `_run_menu` builds, captured without opening the menu."""
    captured: dict[str, tui.Archiver] = {}

    class _Capture:
        def __init__(self, _jobs: object, **kwargs: object) -> None:
            captured["archiver"] = cast("tui.Archiver", kwargs["archiver"])

        def run(self) -> tui.MenuChoice | None:
            return None

    monkeypatch.setattr(app.sys, "stdin", _Tty())
    monkeypatch.setattr(app.sys, "stdout", _Tty())
    monkeypatch.setattr(tui, "MenuApp", _Capture)
    app._run_menu()
    return captured["archiver"]


def test_the_injected_archiver_exports_and_reports_where(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Export(ExportWorkflowUseCase):
        def execute(self, name: str) -> str:
            return str(tmp_path / f"{name}.zip")

    monkeypatch.setattr(app, "build_export_workflow", lambda: _Export())

    assert "nightly.zip" in _built_archiver(monkeypatch).export("nightly")


def test_an_export_failure_is_reported_rather_than_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Export(ExportWorkflowUseCase):
        def execute(self, name: str) -> str:
            raise WorkflowNotFoundError("error.workflow.not_found", name=name)

    monkeypatch.setattr(app, "build_export_workflow", lambda: _Export())

    message = _built_archiver(monkeypatch).export("gone")
    assert message.startswith("✗")
    assert "gone" in message


def _import_returning(result: ImportWorkflowResult) -> type[ImportWorkflowUseCase]:
    class _Import(ImportWorkflowUseCase):
        def execute(self, archive: str, *, replace: bool = False) -> ImportWorkflowResult:
            return result

    return _Import


def test_the_injected_archiver_installs_and_reports_it(monkeypatch: pytest.MonkeyPatch) -> None:
    result = ImportWorkflowResult(ImportOutcome.IMPORTED, "nightly", "/w/nightly")
    monkeypatch.setattr(app, "build_import_workflow", lambda: _import_returning(result)())

    attempt = _built_archiver(monkeypatch).install("/tmp/a.zip", False)

    assert attempt.needs_confirmation is False
    assert "nightly" in attempt.message


def test_a_name_clash_asks_rather_than_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The use case reports the clash; the menu turns that into a question, not an error."""
    result = ImportWorkflowResult(ImportOutcome.REFUSED, "nightly", "/w/nightly")
    monkeypatch.setattr(app, "build_import_workflow", lambda: _import_returning(result)())

    attempt = _built_archiver(monkeypatch).install("/tmp/a.zip", False)

    assert attempt.needs_confirmation is True
    assert "already exists" in attempt.message


def test_a_replacement_names_the_backup_it_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    result = ImportWorkflowResult(ImportOutcome.REPLACED, "nightly", "/w/nightly", "/backups/n")
    monkeypatch.setattr(app, "build_import_workflow", lambda: _import_returning(result)())

    attempt = _built_archiver(monkeypatch).install("/tmp/a.zip", True)

    assert "/backups/n" in attempt.message


def test_an_unreadable_archive_is_reported_rather_than_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Import(ImportWorkflowUseCase):
        def execute(self, archive: str, *, replace: bool = False) -> ImportWorkflowResult:
            raise ArchiveUnreadableError("error.archive.unreadable", archive=archive)

    monkeypatch.setattr(app, "build_import_workflow", lambda: _Import())

    attempt = _built_archiver(monkeypatch).install("/tmp/broken.zip", False)
    assert attempt.message.startswith("✗")
    assert attempt.needs_confirmation is False


# --------------------------------------------------------------------------- #
# The client a launch was pointed at (#79, #80)                                #
# --------------------------------------------------------------------------- #


def _launched_client(monkeypatch: pytest.MonkeyPatch, choice: tui.MenuChoice) -> str:
    """The client `_act_on_tui_choice` ends up launching ``choice`` on."""
    seen: list[str] = []

    def _launch(
        _job: str, _resume: bool, _session: str | None, _cwd: str | None, client: str
    ) -> int:
        seen.append(client)
        return 0

    def _run(_workflow: str, client: str) -> int:
        seen.append(client)
        return 0

    def _new(_workflow: str | None, client: str, _guided: bool) -> int:
        seen.append(client)
        return 0

    def _edit(_workflow: str, client: str, _guided: bool) -> int:
        seen.append(client)
        return 0

    monkeypatch.setattr(app, "_tui_launch_job", _launch)
    monkeypatch.setattr(app, "_run_workflow", _run)
    monkeypatch.setattr(app, "_new_workflow", _new)
    monkeypatch.setattr(app, "_edit_workflow", _edit)
    app._act_on_tui_choice(choice)
    return seen[0]


def test_a_job_launches_on_the_client_the_menu_picked(monkeypatch: pytest.MonkeyPatch) -> None:
    choice = tui.MenuChoice(action="start", job="alpha", client="cursor")
    assert _launched_client(monkeypatch, choice) == "cursor"


def test_a_workflow_run_launches_on_the_client_the_menu_picked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    choice = tui.MenuChoice(action="run", workflow="nightly", client="codex")
    assert _launched_client(monkeypatch, choice) == "codex"


def test_authoring_launches_on_the_client_the_menu_picked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    new = tui.MenuChoice(action="workflow_new", client="cursor")
    edit = tui.MenuChoice(action="workflow_edit", workflow="nightly", client="cursor")
    assert _launched_client(monkeypatch, new) == "cursor"
    assert _launched_client(monkeypatch, edit) == "cursor"


def test_no_pick_falls_back_to_the_configured_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """A launch that never went through the picker behaves exactly as it always did."""

    def _default(_raw: str | None) -> str:
        return "claude"

    monkeypatch.setattr(app, "_client", _default)
    choice = tui.MenuChoice(action="start", job="alpha")
    assert _launched_client(monkeypatch, choice) == "claude"


def test_a_pick_is_not_written_back_as_the_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Per-launch, like --client: choosing once must not change what tomorrow launches on."""
    monkeypatch.setattr(toml_config_reader, "config_path", lambda: tmp_path / "config.toml")
    (tmp_path / "config.toml").write_text('[client]\ndefault = "claude"\n', encoding="utf-8")

    assert _launched_client(monkeypatch, tui.MenuChoice(action="start", job="a", client="codex"))
    assert 'default = "claude"' in (tmp_path / "config.toml").read_text(encoding="utf-8")


def test_the_menu_is_given_the_clients_a_launch_can_use(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Capture:
        def __init__(self, _jobs: object, **kwargs: object) -> None:
            captured["clients"] = kwargs["launch_clients"]

        def run(self) -> tui.MenuChoice | None:
            return None

    class _Launch(ListLaunchClientsUseCase):
        def execute(self) -> list[LaunchClient]:
            return [LaunchClient("claude", "Claude Code", is_default=True)]

    monkeypatch.setattr(app.sys, "stdin", _Tty())
    monkeypatch.setattr(app.sys, "stdout", _Tty())
    monkeypatch.setattr(tui, "MenuApp", _Capture)
    monkeypatch.setattr(app, "build_list_launch_clients", lambda: _Launch())
    app._run_menu()

    listing = cast("Callable[[], list[tui.ClientChoice]]", captured["clients"])
    (only,) = listing()
    assert (only.name, only.display, only.is_default, only.custom) == (
        "claude",
        "Claude Code",
        True,
        False,
    )


def test_build_list_launch_clients_is_wired() -> None:
    assert isinstance(composition.build_list_launch_clients(), ListLaunchClientsUseCase)


def _client(name: str) -> ClientInfo:
    """The packaged catalogue entry for *name* — these tests assume it exists."""
    info = TomlClientCatalogAdapter().by_name(name)
    assert info is not None
    return info


def test_a_job_that_could_not_be_removed_is_reported_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The receipt: the row the user already read, back again, marked."""
    kept = replace(_job_footprint(), removed=False)
    fake = _FakeDeleteJobs(
        [_job_footprint("alpha"), _job_footprint("beta")], outcome=[kept, _job_footprint("beta")]
    )
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)

    assert app.main(["jobs", "delete", "alpha", "beta", "--yes"]) == 1
    err = capsys.readouterr().err
    assert "not removed" in err
    assert "removed 1 of 2 job(s)" in err


def test_a_fully_successful_job_delete_says_nothing_about_leftovers(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeDeleteJobs([_job_footprint()])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)

    assert app.main(["jobs", "delete", "alpha", "--yes"]) == 0
    assert "not removed" not in capsys.readouterr().err


def test_a_session_that_could_not_be_removed_is_reported_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    kept = replace(_session_footprint(), removed=False)
    fake = _FakeDeleteSessions([_session_footprint()], outcome=[kept])
    monkeypatch.setattr(app, "build_delete_sessions", lambda: fake)

    assert app.main(["sessions", "alpha", "delete", "alpha_002", "--yes"]) == 1
    err = capsys.readouterr().err
    assert "not removed" in err
    assert "removed 0 of 1 session(s)" in err
