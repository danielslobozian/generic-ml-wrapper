# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the CLI inbound adapter."""

import io
import json
import platform
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import SettingsUnreadableError
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.domain.model.axis import AxisSelection
from generic_ml_wrapper.application.domain.model.migration import MigrationReport
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.port.inbound.bootstrap import Bootstrap
from generic_ml_wrapper.application.port.inbound.check_client_ready import (
    CheckClientReady,
    ClientReadiness,
)
from generic_ml_wrapper.application.port.inbound.config_commands import ConfigCommands
from generic_ml_wrapper.application.port.inbound.edit_workflow import (
    EditWorkflow,
    EditWorkflowCommand,
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.export_usage import (
    ExportUsage,
    ModelTotal,
    SessionCost,
    TurnRow,
    UsageReport,
)
from generic_ml_wrapper.application.port.inbound.init import Init, InitOutcome
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary, ListJobs
from generic_ml_wrapper.application.port.inbound.list_personas import ListPersonas
from generic_ml_wrapper.application.port.inbound.list_plugins import ListPlugins
from generic_ml_wrapper.application.port.inbound.list_sessions import ListSessions, SessionSummary
from generic_ml_wrapper.application.port.inbound.list_workflows import ListWorkflows
from generic_ml_wrapper.application.port.inbound.migrate_layout import MigrateLayout
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflow,
    NewWorkflowCommand,
    NewWorkflowResult,
    WorkflowExistsError,
    WorkflowOutcome,
)
from generic_ml_wrapper.application.port.inbound.render_greeting import RenderGreeting
from generic_ml_wrapper.application.port.inbound.render_statusline import RenderStatusline
from generic_ml_wrapper.application.port.inbound.set_credential import (
    SetCredential,
    SetCredentialCommand,
)
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJob,
    StartJobCommand,
    StartJobResult,
    UnknownWorkflowError,
)
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
        "run": ["run"],
        "jobs": ["jobs"],
        "sessions": ["sessions", "J"],
        "export": ["export", "J"],
        "statusline": ["statusline"],
        "workflow": ["workflow"],
        "persona": ["persona"],
        "plugins": ["plugins"],
        "creds": ["creds"],
        "config": ["config"],
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

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=3, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    exit_code = app.main(["start", "JOB-9", "--resume-latest"])

    assert exit_code == 3
    assert seen["command"] == StartJobCommand(job="JOB-9", client="claude", resume_latest=True)


def test_start_passes_the_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            seen["command"] = command
            return StartJobResult(exit_code=0, job=command.job, session_id=f"{command.job}_001")

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    app.main(["start", "JOB-1", "--workflow", "doc-review"])

    assert seen["command"].workflow == "doc-review"


def test_start_reports_unknown_workflow_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(StartJob):
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

    class FakeUseCase(StartJob):
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
    class FailingUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> StartJobResult:
            raise UnknownWorkflowError("unknown workflow: 'missing'")

    monkeypatch.setattr(app, "build_start_job", lambda: FailingUseCase())
    assert app.main(["run", "missing"]) == 2
    assert "unknown workflow" in capsys.readouterr().out


class _FakeWorkflows(ListWorkflows):
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

    class FakeUseCase(StartJob):
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
    class FakeUseCase(ListJobs):
        def execute(self) -> list[JobSummary]:
            return [JobSummary("JOB-7", 3)]

    monkeypatch.setattr(app, "build_list_jobs", lambda: FakeUseCase())
    assert app.main(["jobs", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"job": "JOB-7", "session_count": 3}]


def test_jobs_command_json_empty_is_an_empty_array(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListJobs):
        def execute(self) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: FakeUseCase())
    assert app.main(["jobs", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []  # not the "No jobs yet" hint


def test_build_list_jobs_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_jobs(), ListJobs)


def test_format_sessions_empty() -> None:
    assert "No sessions" in app.format_sessions("JOB-1", [])


def test_format_sessions_lists_each() -> None:
    text = app.format_sessions("JOB-1", [SessionSummary("JOB-1_001", "claude")])
    assert "JOB-1 — 1 session(s):" in text
    assert "JOB-1_001" in text
    assert "claude" in text


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
    assert json.loads(capsys.readouterr().out) == [{"session_id": "JOB-1_001", "client": "claude"}]


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
        def execute(self) -> list[JobSummary]:
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
        def execute(self) -> list[JobSummary]:
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


def test_workflow_new_aborts_when_client_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_new_workflow", lambda: None)
    readiness = ClientReadiness(
        client="codex", ready=False, missing=client_catalog.CODEX, installed=()
    )
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient(readiness))
    assert app.main(["workflow", "new", "doc-review", "--client", "codex"]) == 2
    assert client_catalog.CODEX.install_for(platform.system()) in capsys.readouterr().err


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
    class _Workflows(ListWorkflows):
        def execute(self) -> list[str]:
            return []

    monkeypatch.setattr(app, "build_list_workflows", lambda: _Workflows())
    assert app.main(["workflow", "list"]) == 0
    assert "usage: gmlw workflow" not in capsys.readouterr().out  # it ran, not helped


def _deploying_use_case(seen: dict[str, NewWorkflowCommand]) -> NewWorkflow:
    class FakeUseCase(NewWorkflow):
        def execute(self, command: NewWorkflowCommand) -> NewWorkflowResult:
            seen["command"] = command
            return NewWorkflowResult(
                exit_code=0,
                outcome=WorkflowOutcome.DEPLOYED,
                name=command.name or "nightly-etl",
                draft_path="/drafts/create-workflow_001",
            )

    return FakeUseCase()


def test_workflow_new_dispatches_to_the_use_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, NewWorkflowCommand] = {}
    monkeypatch.setattr(app, "build_new_workflow", lambda: _deploying_use_case(seen))
    assert app.main(["workflow", "new", "doc-review"]) == 0
    assert seen["command"] == NewWorkflowCommand(name="doc-review", client="claude")
    assert "created" in capsys.readouterr().err  # the deployed announcement


def test_workflow_new_without_a_name_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, NewWorkflowCommand] = {}
    monkeypatch.setattr(app, "build_new_workflow", lambda: _deploying_use_case(seen))
    assert app.main(["workflow", "new"]) == 0
    assert seen["command"] == NewWorkflowCommand(name=None, client="claude")  # name optional


def test_workflow_new_reports_a_seed_name_collision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(NewWorkflow):
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
    class IncompleteUseCase(NewWorkflow):
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
    assert isinstance(composition.build_new_workflow(), NewWorkflow)


def test_format_workflows_empty() -> None:
    assert "No workflows yet" in app.format_workflows([])


def test_format_workflows_lists_each() -> None:
    text = app.format_workflows(["doc-review", "release"])
    assert "2 workflow(s):" in text
    assert "doc-review" in text
    assert "release" in text


def test_workflow_list_prints_the_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListWorkflows):
        def execute(self) -> list[str]:
            return ["doc-review"]

    monkeypatch.setattr(app, "build_list_workflows", lambda: FakeUseCase())
    assert app.main(["workflow", "list"]) == 0
    assert "doc-review" in capsys.readouterr().out


def test_workflow_list_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeUseCase(ListWorkflows):
        def execute(self) -> list[str]:
            return ["doc-review", "release"]

    monkeypatch.setattr(app, "build_list_workflows", lambda: FakeUseCase())
    assert app.main(["workflow", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == ["doc-review", "release"]


def test_build_list_workflows_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_list_workflows(), ListWorkflows)


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


def test_workflow_edit_dispatches_to_the_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, EditWorkflowCommand] = {}

    class FakeUseCase(EditWorkflow):
        def execute(self, command: EditWorkflowCommand) -> int:
            seen["command"] = command
            return 0

    monkeypatch.setattr(app, "build_edit_workflow", lambda: FakeUseCase())
    assert app.main(["workflow", "edit", "doc-review"]) == 0
    assert seen["command"] == EditWorkflowCommand(name="doc-review", client="claude")


def test_workflow_edit_reports_a_missing_workflow(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(EditWorkflow):
        def execute(self, command: EditWorkflowCommand) -> int:
            raise WorkflowNotFoundError("unknown workflow: 'missing'")

    monkeypatch.setattr(app, "build_edit_workflow", lambda: FailingUseCase())
    assert app.main(["workflow", "edit", "missing"]) == 2
    assert "unknown workflow" in capsys.readouterr().out


def test_build_edit_workflow_is_wired() -> None:
    assert isinstance(composition.build_edit_workflow(), EditWorkflow)
