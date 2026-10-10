# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the CLI inbound adapter."""

import io
import json
import platform
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.inbound.tui import menu_app as tui
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import SettingsUnreadableError
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.domain.model.axis import AxisKind, AxisSelection
from generic_ml_wrapper.application.domain.model.incident import Incident, IncidentKind
from generic_ml_wrapper.application.domain.model.migration import MigrationReport
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
from generic_ml_wrapper.application.port.inbound.bootstrap import Bootstrap
from generic_ml_wrapper.application.port.inbound.check_client_ready import (
    CheckClientReady,
    ClientReadiness,
)
from generic_ml_wrapper.application.port.inbound.config_commands import ConfigCommands
from generic_ml_wrapper.application.port.inbound.create_axis import (
    AxisExistsError,
    CreateAxis,
    CreateAxisCommand,
    CreateAxisResult,
)
from generic_ml_wrapper.application.port.inbound.delete_jobs import DeleteJobs, JobFootprint
from generic_ml_wrapper.application.port.inbound.delete_sessions import (
    DeleteSessions,
    NoSuchJobError,
    NoSuchSessionError,
    SessionFootprint,
)
from generic_ml_wrapper.application.port.inbound.export_usage import (
    AgentTotal,
    ExportUsage,
    ModelTotal,
    SessionCost,
    TurnRow,
    UsageReport,
)
from generic_ml_wrapper.application.port.inbound.init import Init, InitOutcome
from generic_ml_wrapper.application.port.inbound.list_attachments import (
    AttachmentListing,
    ListAttachments,
)
from generic_ml_wrapper.application.port.inbound.list_clients import ClientStatus, ListClients
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary, ListJobs
from generic_ml_wrapper.application.port.inbound.list_launch_clients import (
    LaunchClient,
    ListLaunchClients,
)
from generic_ml_wrapper.application.port.inbound.list_personas import ListPersonas
from generic_ml_wrapper.application.port.inbound.list_plugins import ListPlugins
from generic_ml_wrapper.application.port.inbound.list_sessions import ListSessions, SessionSummary
from generic_ml_wrapper.application.port.inbound.migrate_layout import MigrateLayout
from generic_ml_wrapper.application.port.inbound.render_greeting import RenderGreeting
from generic_ml_wrapper.application.port.inbound.render_statusline import RenderStatusline
from generic_ml_wrapper.application.port.inbound.report_health import (
    DayHealth,
    HealthReport,
    ReportHealth,
)
from generic_ml_wrapper.application.port.inbound.set_credential import (
    SetCredential,
    SetCredentialCommand,
)
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJob,
    StartJobCommand,
    StartJobResult,
)
from generic_ml_wrapper.application.port.inbound.tag_jobs import TagJobs
from generic_ml_wrapper.application.wiring import composition
from generic_ml_wrapper.common import paths
from generic_ml_wrapper.common.i18n import load_localizer


class _RecordingBootstrap(Bootstrap):
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


class _FakeMigrate(MigrateLayout):
    def __init__(self, report: MigrationReport | None = None) -> None:
        self._report = report if report is not None else MigrationReport(environment="work")

    def execute(self) -> MigrationReport:
        return self._report


class _CheckClient(CheckClientReady):
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
    monkeypatch.setattr(app.config, "init_version", _init_done)
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
        "jobs": ["jobs"],
        "sessions": ["sessions", "J"],
        "export": ["export", "J"],
        "health": ["health"],
        "clients": ["clients"],
        "statusline": ["statusline"],
        "tui": ["tui"],
        "attachment": ["attachment"],
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

    class FakeUseCase(StartJob):
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
    assert app._client(None) == app.config.default_client()
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
    monkeypatch.setattr(app.config, "init_version", _init_absent)
    seen: list[str] = []

    class _Init(Init):
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


class _FreshInit(Init):
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
    monkeypatch.setattr(app.config, "init_version", _init_absent)
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
    assert "job-vs-attachment" in out
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

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=3, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    exit_code = app.main(["start", "JOB-9", "--resume-latest"])

    assert exit_code == 3
    assert seen["command"] == StartJobCommand(job="JOB-9", client="claude", resume_latest=True)


@pytest.mark.parametrize(
    ("value", "name", "version"),
    [("notes", "notes", None), ("notes@1.2.0", "notes", "1.2.0"), ("notes@", "notes", "")],
)
def test_start_passes_the_attachment(
    monkeypatch: pytest.MonkeyPatch, value: str, name: str, version: str | None
) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    app.main(["start", "JOB-1", "--attach", value])

    assert (seen["command"].attachment, seen["command"].attachment_version) == (name, version)


def test_start_reports_an_unknown_attachment_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _installed(_client: str) -> bool:
        return True  # no client needed: the attachment is refused first

    monkeypatch.setattr(app, "_preflight_client", _installed)
    assert app.main(["start", "JOB-1", "--attach", "missing"]) == 2
    assert "no attachment named 'missing'" in capsys.readouterr().out


def test_start_reports_resume_not_supported_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            raise ResumeNotSupportedError("session resume not supported on codex")

    monkeypatch.setattr(app, "build_start_job", lambda: FailingUseCase())
    assert app.main(["start", "JOB-1", "--client", "codex", "--resume-latest"]) == 2
    assert "session resume not supported on codex" in capsys.readouterr().out


def test_build_start_job_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_start_job(), StartJob)


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
    class FakeUseCase(ListJobs):
        def execute(self, tag: str | None = None) -> list[JobSummary]:
            return [JobSummary("JOB-7", 3)]

    monkeypatch.setattr(app, "build_list_jobs", lambda: FakeUseCase())
    assert app.main(["jobs"]) == 0
    out = capsys.readouterr().out
    assert "JOB-7" in out
    assert "3 session(s)" in out


def test_jobs_command_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListJobs):
        def execute(self, tag: str | None = None) -> list[JobSummary]:
            return [JobSummary("JOB-7", 3)]

    monkeypatch.setattr(app, "build_list_jobs", lambda: FakeUseCase())
    assert app.main(["jobs", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"job": "JOB-7", "session_count": 3, "tags": []}]


class _FakeListClients(ListClients):
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
    assert isinstance(composition.build_list_clients(), ListClients)


def test_jobs_command_json_empty_is_an_empty_array(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListJobs):
        def execute(self, tag: str | None = None) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: FakeUseCase())
    assert app.main(["jobs", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []  # not the "No jobs yet" hint


def test_build_list_jobs_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_jobs(), ListJobs)


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


def test_format_sessions_shows_the_attachment_a_session_ran() -> None:
    text = app.format_sessions(
        "JOB-1",
        [
            SessionSummary("JOB-1_001", "claude", cwd="/work/a", attachment="feature@1.0.0"),
            SessionSummary("JOB-1_002", "claude", cwd="/work/a"),
        ],
    )
    first, second = text.splitlines()[2:]
    assert "feature@1.0.0" in first
    assert "—" in second  # a plain session says so rather than leaving a gap


def test_format_sessions_shows_folder_fallback_and_not_resumable() -> None:
    text = app.format_sessions(
        "JOB-1", [SessionSummary("JOB-1_002", "codex", cwd=None, resumable=False)]
    )
    assert "(folder unknown)" in text  # no stored folder
    assert "no" in text  # not resumable


def test_sessions_command_prints_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListSessions):
        def execute(self, job: str) -> list[SessionSummary]:
            return [SessionSummary("JOB-1_001", "claude")]

    monkeypatch.setattr(app, "build_list_sessions", lambda: FakeUseCase())
    assert app.main(["sessions", "JOB-1"]) == 0
    assert "JOB-1_001" in capsys.readouterr().out


def test_sessions_command_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListSessions):
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
            "attachment": None,
            "incidents": 0,
        }
    ]


def test_build_list_sessions_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_sessions(), ListSessions)


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


def test_format_usage_without_agents_shows_no_agent_column_or_section() -> None:
    text = app.format_usage(_report())
    assert "totals by agent" not in text
    assert "main" not in text


def test_format_usage_names_who_made_each_turn_and_totals_by_agent() -> None:
    agent = TurnRole.AGENT
    report = UsageReport(
        "JOB-1",
        turns=(
            TurnRow(0.0, "gpt", 1.0, 10, 1, 0, "t1"),
            TurnRow(0.0, "gpt", 1.0, 20, 2, 0, "t2", role=agent, agent="search_space"),
            TurnRow(0.0, "gpt", 1.0, 30, 3, 0, "t3", role=agent),
        ),
        models=(ModelTotal("gpt", 3, 60, 6, 0, 3.0),),
        agents=(
            AgentTotal(TurnRole.MAIN, None, 1, 10, 1, 0, 1.0),
            AgentTotal(agent, None, 1, 30, 3, 0, 1.0),
            AgentTotal(agent, "search_space", 1, 20, 2, 0, 1.0),
        ),
        turn_count=3,
    )
    text = app.format_usage(report)
    rows = text.splitlines()
    assert any("main          gpt" in row and "[t1]" in row for row in rows)
    assert any("search_space  gpt" in row and "[t2]" in row for row in rows)
    assert any("agent         gpt" in row and "[t3]" in row for row in rows)
    assert "── totals by agent ──" in text
    assert "  search_space    1 call(s)  20+2 tok  1.0s" in rows


def test_format_usage_unmetered_timestamp_shows_dashes() -> None:
    assert "--:--:--" in app.format_usage(_report())  # timestamp 0.0 → placeholder


def test_export_command_prints_the_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ExportUsage):
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
    class FakeUseCase(ExportUsage):
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
    assert isinstance(composition.build_export_usage(), ExportUsage)


def test_statusline_command_reads_stdin_env_and_prints(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, str | None] = {}

    class FakeUseCase(RenderStatusline):
        def execute(self, payload_json: str, job: str | None, session: str | None) -> str:
            seen["payload"] = payload_json
            seen["job"] = job
            return "Opus 4.8  ·  $0.43"

    def _build_statusline(*_: object) -> FakeUseCase:
        return FakeUseCase()

    monkeypatch.setattr(app, "build_render_statusline", _build_statusline)
    monkeypatch.setenv("GMLW_JOB", "JOB-1")
    monkeypatch.setattr(app.sys, "stdin", io.StringIO('{"cost": {"total_cost_usd": 0.43}}'))

    assert app.main(["statusline"]) == 0
    assert seen["job"] == "JOB-1"
    assert '"total_cost_usd": 0.43' in (seen["payload"] or "")
    assert "$0.43" in capsys.readouterr().out


def test_build_render_statusline_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_render_statusline(), RenderStatusline)


def test_cursor_plan_cache_is_merged_into_the_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = tmp_path / "cursor-plan.json"
    cache.write_text('{"auto_pct": 6.2, "api_pct": 3.4}', encoding="utf-8")
    monkeypatch.setattr(app.paths, "CURSOR_PLAN", cache)
    merged = app._with_cursor_plan('{"model": {"display_name": "Composer"}}', "cursor")
    assert json.loads(merged)["plan"] == {"auto_pct": 6.2, "api_pct": 3.4}


def test_cursor_plan_untouched_for_other_clients_or_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = tmp_path / "cursor-plan.json"
    cache.write_text('{"auto_pct": 1}', encoding="utf-8")
    monkeypatch.setattr(app.paths, "CURSOR_PLAN", cache)
    assert app._with_cursor_plan("{}", "claude") == "{}"  # not cursor
    kept = '{"plan": {"auto_pct": 9}}'
    assert app._with_cursor_plan(kept, "cursor") == kept  # payload already carries a plan


def test_statusline_renders_the_cursor_plan_block_end_to_end(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    cache = tmp_path / "cursor-plan.json"
    cache.write_text('{"auto_pct": 6, "api_pct": 3}', encoding="utf-8")
    monkeypatch.setattr(app.paths, "CURSOR_PLAN", cache)
    monkeypatch.setenv("GMLW_CLIENT", "cursor")
    monkeypatch.setattr(app.sys, "stdin", io.StringIO('{"model": {"display_name": "Composer"}}'))
    assert app.main(["statusline"]) == 0  # real cursor parser + renderer
    assert "plan auto 6% · api 3%" in capsys.readouterr().out


def test_main_self_initializes_on_a_real_command(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(calls))

    class _Jobs(ListJobs):
        def execute(self, tag: str | None = None) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())
    assert app.main(["jobs"]) == 0
    assert calls == ["init"]


def test_main_skips_self_init_for_statusline(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(calls))

    class _Status(RenderStatusline):
        def execute(self, payload_json: str, job: str | None, session: str | None) -> str:
            return ""

    def _build_status(*_: object) -> _Status:
        return _Status()

    monkeypatch.setattr(app, "build_render_statusline", _build_status)
    monkeypatch.setattr(app.sys, "stdin", io.StringIO(""))
    assert app.main(["statusline"]) == 0
    assert calls == []


class _FakeInit(Init):
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
    class _Jobs(ListJobs):
        def execute(self, tag: str | None = None) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())


def test_gate_forces_init_when_uninitialised(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    boot: list[str] = []
    ran: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(boot))
    monkeypatch.setattr(app.config, "init_version", _init_absent)
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
    monkeypatch.setattr(app.config, "init_version", _init_absent)
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
    monkeypatch.setattr(app.config, "init_version", _init_done)
    monkeypatch.setattr(app, "build_init", lambda: pytest.fail("init must not run"))
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    assert boot == ["init"]  # only bootstrap ran


def test_init_command_runs_the_use_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ran: list[str] = []
    monkeypatch.setattr(app.config, "init_version", _init_done)  # even when already done
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
    monkeypatch.setattr(app.config, "init_version", _init_absent)  # fresh
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(_fresh_outcome(), ran))
    assert app.main(["init"]) == 0
    assert ran == ["init"]  # init ran exactly once
    assert boot == []  # bootstrap never ran


def test_init_announces_no_client_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app.config, "init_version", _init_absent)
    monkeypatch.setattr(
        app, "build_init", lambda: _FakeInit(_fresh_outcome(client=None, found=[]), [])
    )
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    assert "no supported client found on your PATH" in capsys.readouterr().err


def test_init_on_legacy_reports_the_merge_and_any_overwrites(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app.config, "init_version", _init_absent)
    outcome = _fresh_outcome(fresh=False, overwrites=("client.default: cursor → claude",))
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(outcome, []))
    _stub_jobs(monkeypatch)
    assert app.main(["jobs"]) == 0
    err = capsys.readouterr().err
    assert "your choices were saved into" in err
    assert "client.default: cursor → claude" in err  # the replaced value is surfaced


def test_build_init_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_init(), Init)


def test_init_announces_the_chosen_persona(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app.config, "init_version", _init_absent)
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
    monkeypatch.setattr(app.config, "init_version", _init_absent)
    monkeypatch.setattr(app, "build_init", lambda: _FakeInit(_fresh_outcome(), []))
    report = MigrationReport(environment="work", moved=["co.md"])
    monkeypatch.setattr(app, "build_migrate_layout", lambda: _FakeMigrate(report))
    assert app.main(["init"]) == 0
    err = capsys.readouterr().err
    assert "set up — speaking en" in err  # init announced
    assert "migrated 1 item(s)" in err  # and migration ran after it


def test_build_migrate_layout_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_migrate_layout(), MigrateLayout)


def test_start_does_not_print_the_greeting_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The host greeting is now injected into the session context (rendered in-band by the
    # client), not printed to the launch-time stderr that the client immediately clears.
    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["start", "JOB-1"]) == 0
    assert "# Greeting" not in capsys.readouterr().err  # no greeting on stderr anymore


def test_build_render_greeting_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_render_greeting(), RenderGreeting)


def test_start_aborts_with_guidance_when_client_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    launched: list[str] = []

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            launched.append(command.job)
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    readiness = ClientReadiness(
        client="cursor", ready=False, missing=client_catalog.CURSOR, installed=()
    )
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
    readiness = ClientReadiness(
        client="claude", ready=False, missing=client_catalog.CLAUDE, installed=("codex",)
    )
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient(readiness))
    assert app.main(["start", "JOB-1"]) == 2
    assert "--client codex" in capsys.readouterr().err  # suggest the one they have


def test_start_lists_all_when_no_client_installed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_start_job", lambda: None)
    readiness = ClientReadiness(
        client="claude", ready=False, missing=client_catalog.CLAUDE, installed=()
    )
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient(readiness))
    assert app.main(["start", "JOB-1"]) == 2
    err = capsys.readouterr().err
    for info in client_catalog.SUPPORTED:  # every supported client's install is offered
        assert info.install_for(platform.system()) in err


def test_build_check_client_ready_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_check_client_ready(), CheckClientReady)


def test_start_aborts_cleanly_when_the_cwd_is_deleted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _dead_cwd() -> str:
        raise FileNotFoundError

    monkeypatch.setattr(app.os, "getcwd", _dead_cwd)
    monkeypatch.setattr(app, "build_start_job", lambda: None)  # must never be reached
    assert app.main(["start", "JOB-1"]) == 2
    assert "current directory no longer exists" in capsys.readouterr().err


def test_creds_set_reads_stdin_and_stores_without_echoing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, SetCredentialCommand] = {}

    class FakeUseCase(SetCredential):
        def execute(self, command: SetCredentialCommand) -> None:
            seen["command"] = command

    monkeypatch.setattr(app, "build_set_credential", lambda: FakeUseCase())
    monkeypatch.setattr(app.sys, "stdin", io.StringIO("ghp_secret\n"))

    assert app.main(["creds", "set", "doc-review", "GITHUB_TOKEN"]) == 0
    assert seen["command"] == SetCredentialCommand("doc-review", "GITHUB_TOKEN", "ghp_secret")
    out = capsys.readouterr().out
    assert "stored doc-review.GITHUB_TOKEN" in out
    assert "ghp_secret" not in out  # the secret is never echoed


def test_build_set_credential_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_set_credential(), SetCredential)


def test_incomplete_subcommand_prints_its_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["attachment"]) == 0  # no action -> auto help
    out = capsys.readouterr().out
    assert "usage: gmlw attachment" in out
    assert "import" in out
    assert "list" in out


def test_incomplete_persona_and_plugins_print_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["persona"]) == 0
    assert "usage: gmlw persona" in capsys.readouterr().out
    assert app.main(["plugins"]) == 0
    assert "usage: gmlw plugins" in capsys.readouterr().out


def test_complete_subcommand_does_not_print_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _Attachments(ListAttachments):
        def execute(self) -> list[AttachmentListing]:
            return []

    monkeypatch.setattr(app, "build_list_attachments", lambda: _Attachments())
    assert app.main(["attachment", "list"]) == 0
    assert "usage: gmlw attachment" not in capsys.readouterr().out  # it ran, not helped


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
    class FakeUseCase(ListPersonas):
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
    class FakeUseCase(ListPersonas):
        def execute(self) -> list[Persona]:
            return [Persona("butler", "A Jeeves.", "g", "b")]

    monkeypatch.setattr(app, "build_list_personas", lambda: FakeUseCase())
    assert app.main(["persona", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"name": "butler", "description": "A Jeeves."}]


def test_build_list_personas_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_personas(), ListPersonas)


def test_plugins_list_prints_the_plugins(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListPlugins):
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
    class FakeUseCase(ListPlugins):
        def execute(self) -> list[Plugin]:
            return [Plugin("cursor-mitm", "MITM")]

    monkeypatch.setattr(app, "build_list_plugins", lambda: FakeUseCase())
    assert app.main(["plugins", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"id": "cursor-mitm", "description": "MITM"}]


def test_plugins_list_empty_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListPlugins):
        def execute(self) -> list[Plugin]:
            return []

    monkeypatch.setattr(app, "build_list_plugins", lambda: FakeUseCase())
    assert app.main(["plugins", "list"]) == 0
    assert "~/.gmlw/plugins/" in capsys.readouterr().out


def test_build_list_plugins_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_plugins(), ListPlugins)


class _NoBootstrap(Bootstrap):
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
    class FailingUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            raise SettingsUnreadableError(Path("/x/.claude/settings.json"))

    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    monkeypatch.setattr(app, "build_start_job", lambda: FailingUseCase())
    assert app.main(["start", "JOB-1"]) == 2
    assert "is not valid JSON" in capsys.readouterr().err


def test_creds_set_rejects_invalid_attachment_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_bootstrap", lambda: _NoBootstrap())
    assert app.main(["creds", "set", "Bad Name", "TOKEN"]) == 2
    assert "invalid attachment name" in capsys.readouterr().err


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
    assert 'default_role = "reviewer"' in (paths.HOME / "config.toml").read_text(encoding="utf-8")


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
    assert isinstance(composition.build_config_commands(), ConfigCommands)


def test_exit_receipt_prints_cost_and_next_steps(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(StartJob):
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
    class FakeUseCase(StartJob):
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
    (paths.HOME).mkdir(parents=True, exist_ok=True)
    (paths.HOME / "config.toml").write_text("[hints]\nshow = false\n", encoding="utf-8")

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            return StartJobResult(exit_code=0, job=command.job, session_id="JOB-1_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["start", "JOB-1"]) == 0
    assert "tip:" not in capsys.readouterr().err


class _FakeCreateAxis(CreateAxis):
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
    assert isinstance(composition.build_create_axis(), CreateAxis)


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
            path = app.config.config_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[client]\ndefault = "codex"\n', encoding="utf-8")
            return tui.MenuChoice(action="start", job="alpha")

    monkeypatch.setattr(tui, "MenuApp", _MenuSwitchingTheClient)
    launched: list[str] = []

    def _record_launch(
        _job: str,
        _resume: bool,
        _session: str | None,
        _cwd: str | None,
        client: str,
        **_attached: object,
    ) -> int:
        launched.append(client)
        return 0

    monkeypatch.setattr(app, "_tui_launch_job", _record_launch)
    assert app._tui() == 0
    assert launched == ["codex"]  # the switch just made, not the default the menu opened on


# --------------------------------------------------------------------------- #
# Deleting jobs and sessions                                                   #
# --------------------------------------------------------------------------- #


class _FakeDeleteJobs(DeleteJobs):
    """Records what it was asked to preview and delete; deletes nothing."""

    def __init__(self, footprints: list[JobFootprint], error: Exception | None = None) -> None:
        self._footprints = footprints
        self._error = error
        self.previewed: list[list[str]] = []
        self.executed: list[list[str]] = []

    def preview(self, jobs: Sequence[str]) -> list[JobFootprint]:
        if self._error is not None:
            raise self._error
        self.previewed.append(list(jobs))
        return self._footprints

    def execute(self, jobs: Sequence[str]) -> list[JobFootprint]:
        self.executed.append(list(jobs))
        return self._footprints


class _FakeDeleteSessions(DeleteSessions):
    """Records what it was asked to preview and delete; deletes nothing."""

    def __init__(self, footprints: list[SessionFootprint], error: Exception | None = None) -> None:
        self._footprints = footprints
        self._error = error
        self.executed: list[tuple[str, list[str]]] = []

    def preview(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        if self._error is not None:
            raise self._error
        return self._footprints

    def execute(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        self.executed.append((job, list(sessions)))
        return self._footprints


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
    def _unreachable() -> DeleteJobs:
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


def test_jobs_delete_that_leaves_one_behind_says_which_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stuck = replace(_job_footprint("beta"), removed=False)
    fake = _FakeDeleteJobs([_job_footprint("alpha"), stuck])
    monkeypatch.setattr(app, "build_delete_jobs", lambda: fake)

    assert app.main(["jobs", "delete", "alpha", "beta", "--yes"]) == 1
    err = capsys.readouterr().err
    assert "beta" in err
    assert "not removed" in err
    assert "removed 1 of 2 job(s); 1 still there" in err
    # The receipt lists only what stayed, under no "this will remove" heading.
    assert "This will permanently remove" not in err


def test_sessions_delete_that_leaves_one_behind_says_which_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stuck = replace(_session_footprint("alpha_003"), removed=False)
    fake = _FakeDeleteSessions([_session_footprint("alpha_002"), stuck])
    monkeypatch.setattr(app, "build_delete_sessions", lambda: fake)

    assert app.main(["sessions", "alpha", "delete", "alpha_002", "alpha_003", "--yes"]) == 1
    err = capsys.readouterr().err
    assert "alpha_003" in err
    assert "not removed" in err
    assert "removed 1 of 2 session(s) from alpha; 1 still there" in err


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
    assert isinstance(composition.build_delete_jobs(), DeleteJobs)
    assert isinstance(composition.build_delete_sessions(), DeleteSessions)


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
        _job: str,
        _resume: bool,
        _session: str | None,
        _cwd: str | None,
        _client: str,
        **_attached: object,
    ) -> int:
        return 7

    monkeypatch.setattr(app, "_tui_launch_job", _launch)

    code, opened = _drive_tui(
        monkeypatch, _menu_returning(tui.MenuChoice(action="start", job="alpha"))
    )

    assert (code, opened) == (7, 1)  # the exit code is the client's, and the menu never reopened


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

    class _Jobs(ListJobs):
        def execute(self, tag: str | None = None) -> list[JobSummary]:
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
    for action in ("jobs_delete", "sessions_delete", "attachment_export", "attachment_import"):
        assert app._act_on_tui_choice(tui.MenuChoice(action=action)) == 0


# --------------------------------------------------------------------------- #
# The client a launch was pointed at (#79, #80)                                #
# --------------------------------------------------------------------------- #


def _launched_client(monkeypatch: pytest.MonkeyPatch, choice: tui.MenuChoice) -> str:
    """The client `_act_on_tui_choice` ends up launching ``choice`` on."""
    seen: list[str] = []

    def _launch(
        _job: str,
        _resume: bool,
        _session: str | None,
        _cwd: str | None,
        client: str,
        **_attached: object,
    ) -> int:
        seen.append(client)
        return 0

    monkeypatch.setattr(app, "_tui_launch_job", _launch)
    app._act_on_tui_choice(choice)
    return seen[0]


def test_a_job_launches_on_the_client_the_menu_picked(monkeypatch: pytest.MonkeyPatch) -> None:
    choice = tui.MenuChoice(action="start", job="alpha", client="cursor")
    assert _launched_client(monkeypatch, choice) == "cursor"


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
    monkeypatch.setattr(app.config, "config_path", lambda: tmp_path / "config.toml")
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

    class _Launch(ListLaunchClients):
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
    assert isinstance(composition.build_list_launch_clients(), ListLaunchClients)


# --------------------------------------------------------------------------- #
# One place per setting                                                        #
# --------------------------------------------------------------------------- #
def _captured_menu(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Everything `_run_menu` hands the app, captured without opening the menu."""
    captured: dict[str, object] = {}

    class _Capture:
        def __init__(self, _jobs: object, **kwargs: object) -> None:
            captured.update(kwargs)

        def run(self) -> tui.MenuChoice | None:
            return None

    monkeypatch.setattr(app.sys, "stdin", _Tty())
    monkeypatch.setattr(app.sys, "stdout", _Tty())
    monkeypatch.setattr(tui, "MenuApp", _Capture)
    app._run_menu()
    return captured


def test_a_setting_with_its_own_menu_is_not_offered_in_the_config_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # One place per setting: persona, role, environment and the default client are changed
    # on their own screens, so offering them again under Config → Get/Set/List gave two
    # readers of one value that could disagree the moment either wrote.
    captured = _captured_menu(monkeypatch)
    switchers = cast("dict[str, tui.Switcher]", captured["switchers"])
    config = cast("tui.ConfigCatalog", captured["config"])
    offered = {setting.key for setting in config.settings}
    for switcher in switchers.values():
        assert switcher.key not in offered, f"{switcher.key} is offered in two places"
    assert app.CLIENT_DEFAULT_KEY not in offered


def test_every_setting_hidden_from_the_config_views_has_a_menu_of_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The failure that would ship in silence: hide a key with no dedicated screen behind it
    # and the setting becomes unreachable in the TUI, with nothing to say so.
    captured = _captured_menu(monkeypatch)
    switchers = cast("dict[str, tui.Switcher]", captured["switchers"])
    config = cast("tui.ConfigCatalog", captured["config"])
    hidden = {view.key for view in composition.build_config_commands().list()} - {
        setting.key for setting in config.settings
    }
    reachable = {switcher.key for switcher in switchers.values()} | {app.CLIENT_DEFAULT_KEY}
    assert hidden == reachable


def test_a_setting_without_its_own_menu_is_still_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _captured_menu(monkeypatch)
    config = cast("tui.ConfigCatalog", captured["config"])
    assert "logging.level" in {setting.key for setting in config.settings}


# --------------------------------------------------------------------------- #
# Job tags                                                                     #
# --------------------------------------------------------------------------- #
class _RecordingTagJobs(TagJobs):
    """Records what it was asked to do; answers with the tags a test set up."""

    def __init__(self, result: tuple[str, ...] = (), error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[str, str, list[str]]] = []

    def _answer(self, verb: str, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        if self._error is not None:
            raise self._error
        self.calls.append((verb, job, list(tags)))
        return self._result

    def add(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        return self._answer("add", job, tags)

    def remove(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        return self._answer("remove", job, tags)

    def replace(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        return self._answer("replace", job, tags)


def test_jobs_tag_adds_and_prints_the_tags_now_held(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tagger = _RecordingTagJobs(("payments", "sprint-42"))
    monkeypatch.setattr(app, "build_tag_jobs", lambda: tagger)
    assert app.main(["jobs", "tag", "PAY-1", "sprint-42", "payments"]) == 0
    assert tagger.calls == [("add", "PAY-1", ["sprint-42", "payments"])]
    assert "PAY-1: #payments #sprint-42" in capsys.readouterr().out


def test_jobs_untag_removes_and_says_when_none_are_left(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tagger = _RecordingTagJobs(())
    monkeypatch.setattr(app, "build_tag_jobs", lambda: tagger)
    assert app.main(["jobs", "untag", "PAY-1", "sprint-42"]) == 0
    assert tagger.calls == [("remove", "PAY-1", ["sprint-42"])]
    assert "PAY-1: no tags" in capsys.readouterr().out


def test_tagging_an_unknown_job_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = NoSuchJobError("error.job.not_found", job="ghost")
    monkeypatch.setattr(app, "build_tag_jobs", lambda: _RecordingTagJobs(error=error))
    assert app.main(["jobs", "tag", "ghost", "sprint-42"]) == 2
    assert "unknown job" in capsys.readouterr().err


def test_jobs_tag_filter_reaches_the_use_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    asked: list[str | None] = []

    class _Jobs(ListJobs):
        def execute(self, tag: str | None = None) -> list[JobSummary]:
            asked.append(tag)
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())
    assert app.main(["jobs", "--tag", "sprint-42"]) == 0
    assert asked == ["sprint-42"]
    # An empty filtered list says no job carries the tag, not that there are no jobs.
    assert "No job is tagged #sprint-42" in capsys.readouterr().out


def test_format_jobs_shows_each_jobs_tags() -> None:
    text = app.format_jobs(
        [JobSummary("PAY-1", 3, ("payments", "sprint-42")), JobSummary("PAY-2", 1)]
    )
    first, second = text.splitlines()[2:]
    assert first.endswith("#payments #sprint-42")
    assert second.endswith("1 session(s)")  # no trailing gap for an untagged job


def test_start_passes_its_tags_on(monkeypatch: pytest.MonkeyPatch) -> None:
    parsed = app.build_parser().parse_args(
        ["start", "PAY-1", "--tag", "sprint-42", "--tag", "payments"]
    )
    assert parsed.tag == ["sprint-42", "payments"]


@pytest.mark.parametrize(
    ("argv", "hands_over"),
    [
        ([], True),  # bare `gmlw`: the menu, and the usual way into a session
        (["tui"], True),
        (["start", "PAY-1"], True),
        (["PAY-1"], True),  # shorthand for start
        (["jobs"], False),
        (["attachment", "list"], False),
    ],
)
def test_a_command_that_hands_the_terminal_over_logs_nothing_to_it(
    argv: list[str], hands_over: bool
) -> None:
    # While a client owns the screen, stderr is its display: a log line written there is
    # drawn over it and lost on the next redraw. Such a command logs to the file only.
    args = app.build_parser().parse_args(app._implicit_start(argv))
    assert app._hands_over_the_terminal(args) is hands_over


# --------------------------------------------------------------------------- #
# Connection health                                                            #
# --------------------------------------------------------------------------- #
def _incident(kind: IncidentKind = IncidentKind.CONNECTION_LOST) -> Incident:
    return Incident(
        "PAY-1",
        "PAY-1_003",
        kind,
        "TimeoutError: The read operation timed out",
        datetime(2026, 10, 5, 18, 4, 28, tzinfo=UTC).timestamp(),
    )


class _FakeHealth(ReportHealth):
    def __init__(self, report: HealthReport) -> None:
        self.report = report
        self.asked: list[tuple[int, str | None]] = []

    def execute(self, days: int = 7, job: str | None = None) -> HealthReport:
        self.asked.append((days, job))
        return self.report


def test_health_lists_each_day_then_the_latest_incidents(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = HealthReport(
        days=2,
        job=None,
        by_day=(DayHealth("2026-10-06"), DayHealth("2026-10-05", 1, 1)),
        incidents=(_incident(IncidentKind.STREAM_INTERRUPTED), _incident()),
    )
    fake = _FakeHealth(report)
    monkeypatch.setattr(app, "build_report_health", lambda: fake)
    assert app.main(["health", "--days", "2", "--job", "PAY-1"]) == 0
    assert fake.asked == [(2, "PAY-1")]
    out = capsys.readouterr().out
    assert "2026-10-05  1 connection lost · 1 stream cut" in out
    assert "2026-10-06  0 connection lost · 0 stream cut" in out
    assert "PAY-1_003  stream cut  TimeoutError: The read operation timed out" in out


def test_health_says_so_when_all_is_well(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = HealthReport(days=7, job=None, by_day=(), incidents=())
    monkeypatch.setattr(app, "build_report_health", lambda: _FakeHealth(report))
    assert app.main(["health"]) == 0
    assert "No connection incidents" in capsys.readouterr().out


def test_health_json_names_the_kind(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = HealthReport(days=1, job=None, by_day=(), incidents=(_incident(),))
    monkeypatch.setattr(app, "build_report_health", lambda: _FakeHealth(report))
    assert app.main(["health", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["incidents"][0]["kind"] == "connection_lost"


def test_the_export_lists_the_jobs_incidents() -> None:
    text = app.format_usage(
        UsageReport("PAY-1", turn_count=1, incidents=(_incident(), _incident()))
    )
    assert "connection incidents ──  2  (2 connection lost · 0 stream cut)" in text
    assert "TimeoutError: The read operation timed out" in text


def test_a_session_with_incidents_is_marked_in_the_listing() -> None:
    text = app.format_sessions(
        "PAY-1",
        [SessionSummary("PAY-1_001", "claude"), SessionSummary("PAY-1_002", "claude", incidents=3)],
    )
    first, second = text.splitlines()[2:]
    assert "incident" not in first
    assert second.endswith("⚠ 3 incident(s)")


def test_the_export_shows_incidents_even_before_any_turn_was_metered() -> None:
    text = app.format_usage(UsageReport("PAY-1", incidents=(_incident(),)))
    assert "No usage recorded" not in text
    assert "TimeoutError: The read operation timed out" in text


def test_the_menu_health_groups_incidents_by_local_day(monkeypatch: pytest.MonkeyPatch) -> None:
    incident = _incident()
    day = datetime.fromtimestamp(incident.occurred_at).astimezone().date().isoformat()
    report = HealthReport(
        days=2,
        job=None,
        by_day=(DayHealth(day, connection_lost=1), DayHealth("1999-01-01")),
        incidents=(incident,),
    )
    monkeypatch.setattr(app, "build_report_health", lambda: _FakeHealth(report))
    captured = _captured_menu(monkeypatch)
    days = cast("Callable[[], list[tui.HealthDayView]]", captured["health"])()
    assert [(d.day, d.count, d.summary) for d in days] == [
        (day, 1, "1 connection lost · 0 stream cut"),
        ("1999-01-01", 0, "0 connection lost · 0 stream cut"),
    ]
    assert days[0].rows[0][1:] == (
        "PAY-1",
        "PAY-1_003",
        "connection lost",
        "TimeoutError: The read operation timed out",
    )


def _attachment_zip(folder: Path, version: str = "1.0.0") -> Path:
    archive = folder / f"notes-{version}-source.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(
            "manifest.yaml",
            f"name: notes\ndescription: My notes.\nversion: {version}\nmain_md_file: main.md\n",
        )
        zipped.writestr("main.md", "Notes.\n")
    return archive


def test_attachment_import_then_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["attachment", "import", str(_attachment_zip(tmp_path))]) == 0
    assert "imported notes 1.0.0" in capsys.readouterr().err

    assert app.main(["attachment", "list"]) == 0
    out = capsys.readouterr().out
    assert "1 attachment version(s)" in out
    assert "notes  1.0.0  My notes." in out


def test_attachment_list_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    app.main(["attachment", "import", str(_attachment_zip(tmp_path))])
    capsys.readouterr()

    assert app.main(["attachment", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [
        {
            "name": "notes",
            "version": "1.0.0",
            "description": "My notes.",
            "main_md_file": "main.md",
            "intact": True,
        }
    ]


def test_attachment_list_shows_an_invalid_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app.main(["attachment", "import", str(_attachment_zip(tmp_path))])
    folder = paths.ATTACHMENTS / "notes" / "1.0.0"
    folder.chmod(0o755)
    (folder / "extra.md").write_text("x")
    capsys.readouterr()

    assert app.main(["attachment", "list"]) == 0
    assert "changed since its import" in capsys.readouterr().out


def test_attachment_list_empty_hint(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["attachment", "list"]) == 0
    assert "gmlw attachment import <zip>" in capsys.readouterr().out


def test_attachment_import_refuses_a_stored_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app.main(["attachment", "import", str(_attachment_zip(tmp_path))])
    capsys.readouterr()

    assert app.main(["attachment", "import", str(_attachment_zip(tmp_path))]) == 2
    assert "already imported" in capsys.readouterr().err


def test_attachment_export_writes_the_zip_where_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app.main(["attachment", "import", str(_attachment_zip(tmp_path))])
    capsys.readouterr()

    assert app.main(["attachment", "export", "notes", "--to", str(tmp_path / "out")]) == 0

    written = tmp_path / "out" / "notes-1.0.0.zip"
    assert written.is_file()
    assert str(written) in capsys.readouterr().err


def test_attachment_export_of_an_unknown_name_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["attachment", "export", "missing"]) == 2
    assert "no attachment named 'missing'" in capsys.readouterr().err


def test_attachment_delete_with_yes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    app.main(["attachment", "import", str(_attachment_zip(tmp_path))])
    capsys.readouterr()

    assert app.main(["attachment", "delete", "notes", "1.0.0", "--yes"]) == 0

    assert "removed notes 1.0.0" in capsys.readouterr().err
    assert not (paths.ATTACHMENTS / "notes").exists()


def test_attachment_delete_without_a_tty_deletes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app.main(["attachment", "import", str(_attachment_zip(tmp_path))])
    capsys.readouterr()

    assert app.main(["attachment", "delete", "notes", "1.0.0"]) == 2

    err = capsys.readouterr().err
    assert "permanently remove notes 1.0.0" in err
    assert "nothing was deleted" in err
    assert (paths.ATTACHMENTS / "notes" / "1.0.0").is_dir()


@pytest.mark.parametrize(
    ("version", "message"),
    [("9.9.9", "has no version 9.9.9"), ("1.0", "invalid attachment version")],
)
def test_attachment_delete_reports_before_asking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], version: str, message: str
) -> None:
    app.main(["attachment", "import", str(_attachment_zip(tmp_path))])
    capsys.readouterr()

    assert app.main(["attachment", "delete", "notes", version]) == 2

    err = capsys.readouterr().err
    assert message in err
    assert "permanently remove" not in err


def test_attachment_without_an_action_shows_its_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main(["attachment"]) == 0
    assert "import" in capsys.readouterr().out


def test_the_tui_shelf_reaches_the_real_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shelf = app._shelf()  # pyright: ignore[reportPrivateUsage]
    monkeypatch.chdir(tmp_path)

    assert "imported notes 1.0.0" in shelf.import_zip(str(_attachment_zip(tmp_path)))
    assert [(row.key, row.intact) for row in shelf.rows()] == [("notes@1.0.0", True)]
    assert str(tmp_path / "notes-1.0.0.zip") in shelf.export("notes@1.0.0")
    assert shelf.export("notes@1.0.0").startswith("✗")  # already there
    assert "notes 1.0.0" in shelf.preview_delete(("notes@1.0.0",))
    assert "gmlw attachment export notes 1.0.0" in shelf.modify_note("notes@1.0.0")
    assert "removed 1" in shelf.delete(("notes@1.0.0",))
    assert shelf.rows() == []
    assert shelf.import_zip(str(tmp_path / "missing.zip")).startswith("✗")


def test_a_tui_launch_carries_the_attachment_and_the_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    def _installed(_client: str) -> bool:
        return True

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    monkeypatch.setattr(app, "_preflight_client", _installed)

    app._tui_launch_job(  # pyright: ignore[reportPrivateUsage]
        "modify_notes_v1-0-0",
        False,
        None,
        None,
        "claude",
        attachment="workflow-creator",
        attachment_version="1.0.0",
        note="modify notes@1.0.0",
    )

    command = seen["command"]
    assert (command.attachment, command.attachment_version, command.note) == (
        "workflow-creator",
        "1.0.0",
        "modify notes@1.0.0",
    )


def test_legacy_workflows_are_imported_and_announced_on_the_next_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = paths.LEGACY_WORKFLOWS / "doc-review"
    folder.mkdir(parents=True)
    legacy_main = folder / "workflow.md"
    legacy_main.write_text("# doc-review", encoding="utf-8")

    assert app.main(["attachment", "list"]) == 0

    captured = capsys.readouterr()
    assert "now attachments: doc-review@1.0.0" in captured.err
    assert "delete it when you no longer need it" in captured.err
    assert "doc-review  1.0.0" in captured.out
    assert app.main(["attachment", "list"]) == 0
    assert "now attachments" not in capsys.readouterr().err  # once only
