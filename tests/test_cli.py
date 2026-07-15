# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the CLI inbound adapter."""

import io
import json
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import SettingsUnreadableError
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.port.inbound.bootstrap import Bootstrap
from generic_ml_wrapper.application.port.inbound.check_client_ready import (
    CheckClientReady,
    ClientReadiness,
)
from generic_ml_wrapper.application.port.inbound.export_usage import (
    ExportUsage,
    ModelTotal,
    SessionCost,
    TurnRow,
    UsageReport,
)
from generic_ml_wrapper.application.port.inbound.first_run_init import (
    FirstRunInit,
    FirstRunOutcome,
)
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary, ListJobs
from generic_ml_wrapper.application.port.inbound.list_personas import ListPersonas
from generic_ml_wrapper.application.port.inbound.list_plugins import ListPlugins
from generic_ml_wrapper.application.port.inbound.list_sessions import ListSessions, SessionSummary
from generic_ml_wrapper.application.port.inbound.list_workflows import ListWorkflows
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflow,
    NewWorkflowCommand,
    WorkflowExistsError,
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
    UnknownWorkflowError,
)
from generic_ml_wrapper.application.wiring import composition


class _RecordingBootstrap(Bootstrap):
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def execute(self) -> None:
        self._calls.append("init")


def _config_present(*_: object, **__: object) -> bool:
    return True


def _config_absent(*_: object, **__: object) -> bool:
    return False


class _Greeting(RenderGreeting):
    def __init__(self, text: str | None = None) -> None:
        self._text = text

    def execute(self) -> str | None:
        return self._text


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

    Also pin ``config_exists`` to ``True`` so ``main`` takes the (stubbed) bootstrap
    branch, not the first-run branch — first-run wiring is exercised on its own below —
    and stub the host greeting off so ``start`` tests don't read the real config.
    """
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap([]))
    monkeypatch.setattr(app.config, "config_exists", _config_present)
    monkeypatch.setattr(app, "build_render_greeting", lambda: _Greeting(None))
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
        "start": ["start"],
        "jobs": ["jobs"],
        "sessions": ["sessions", "J"],
        "export": ["export", "J"],
        "statusline": ["statusline"],
        "workflow": ["workflow"],
        "persona": ["persona"],
        "plugins": ["plugins"],
        "creds": ["creds"],
    }
    assert set(samples) == app._COMMANDS  # every command has a sample, and vice versa
    for command, argv in samples.items():
        assert parser.parse_args(argv).command == command  # each really parses
        assert app._implicit_start(argv) == argv  # and is never mistaken for a job


def test_bare_job_dispatches_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> int:
            seen["command"] = command
            return 0

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


def test_no_command_prints_help_with_banner(capsys: pytest.CaptureFixture[str]) -> None:
    assert app.main([]) == 0
    out = capsys.readouterr().out
    assert "start" in out
    assert "a wrapper around an ML coding CLI" in out  # banner in the help description


def test_start_dispatches_to_the_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> int:
            seen["command"] = command
            return 3

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    exit_code = app.main(["start", "JOB-9", "--resume-latest"])

    assert exit_code == 3
    assert seen["command"] == StartJobCommand(job="JOB-9", client="claude", resume_latest=True)


def test_start_passes_the_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, StartJobCommand] = {}

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> int:
            seen["command"] = command
            return 0

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    app.main(["start", "JOB-1", "--workflow", "doc-review"])

    assert seen["command"].workflow == "doc-review"


def test_start_reports_unknown_workflow_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> int:
            raise UnknownWorkflowError("unknown workflow: 'missing'")

    monkeypatch.setattr(app, "build_start_job", lambda: FailingUseCase())
    assert app.main(["start", "JOB-1", "--workflow", "missing"]) == 2
    assert "unknown workflow" in capsys.readouterr().out


def test_start_reports_resume_not_supported_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> int:
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


class _FakeFirstRun(FirstRunInit):
    def __init__(self, outcome: FirstRunOutcome, calls: list[str]) -> None:
        self._outcome = outcome
        self._calls = calls

    def execute(self) -> FirstRunOutcome:
        self._calls.append("first-run")
        return self._outcome


def test_main_runs_first_run_init_when_config_absent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    boot: list[str] = []
    first: list[str] = []
    monkeypatch.setattr(app, "build_bootstrap", lambda: _RecordingBootstrap(boot))
    monkeypatch.setattr(app.config, "config_exists", _config_absent)
    monkeypatch.setattr(
        app,
        "build_first_run_init",
        lambda: _FakeFirstRun(FirstRunOutcome(found=["cursor"], chosen="cursor"), first),
    )

    class _Jobs(ListJobs):
        def execute(self) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())
    assert app.main(["jobs"]) == 0
    assert first == ["first-run"]  # first-run ran
    assert boot == []  # bootstrap did not
    err = capsys.readouterr().err
    assert "set 'cursor' as your default client" in err


def test_first_run_announces_no_client_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app.config, "config_exists", _config_absent)
    monkeypatch.setattr(
        app,
        "build_first_run_init",
        lambda: _FakeFirstRun(FirstRunOutcome(found=[], chosen=None), []),
    )

    class _Jobs(ListJobs):
        def execute(self) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())
    assert app.main(["jobs"]) == 0
    assert "no supported client found on your PATH" in capsys.readouterr().err


def test_first_run_is_silent_when_multi_client_unresolved(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app.config, "config_exists", _config_absent)
    monkeypatch.setattr(
        app,
        "build_first_run_init",
        lambda: _FakeFirstRun(FirstRunOutcome(found=["claude", "cursor"], chosen=None), []),
    )

    class _Jobs(ListJobs):
        def execute(self) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())
    assert app.main(["jobs"]) == 0
    assert capsys.readouterr().err == ""  # nothing forced on a non-interactive run


def test_build_first_run_init_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_first_run_init(), FirstRunInit)


def test_first_run_announces_the_chosen_persona(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app.config, "config_exists", _config_absent)
    outcome = FirstRunOutcome(found=["cursor"], chosen="cursor", persona="butler")
    monkeypatch.setattr(app, "build_first_run_init", lambda: _FakeFirstRun(outcome, []))

    class _Jobs(ListJobs):
        def execute(self) -> list[JobSummary]:
            return []

    monkeypatch.setattr(app, "build_list_jobs", lambda: _Jobs())
    assert app.main(["jobs"]) == 0
    assert "persona 'butler' selected" in capsys.readouterr().err


def test_start_prints_the_host_greeting_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_render_greeting", lambda: _Greeting("Good evening, Daniel."))

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> int:
            return 0

    monkeypatch.setattr(app, "build_start_job", lambda: FakeUseCase())
    assert app.main(["start", "JOB-1"]) == 0
    captured = capsys.readouterr()
    assert "Good evening, Daniel." in captured.err  # greeting on stderr, not stdout
    assert "Good evening, Daniel." not in captured.out


def test_build_render_greeting_wires_a_real_use_case() -> None:
    assert isinstance(composition.build_render_greeting(), RenderGreeting)


def test_start_aborts_with_guidance_when_client_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    launched: list[str] = []

    class FakeUseCase(StartJob):
        def execute(self, command: StartJobCommand) -> int:
            launched.append(command.job)
            return 0

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
        assert info.install in err


def test_workflow_new_aborts_when_client_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_new_workflow", lambda: None)
    readiness = ClientReadiness(
        client="codex", ready=False, missing=client_catalog.CODEX, installed=()
    )
    monkeypatch.setattr(app, "build_check_client_ready", lambda: _CheckClient(readiness))
    assert app.main(["workflow", "new", "doc-review", "--client", "codex"]) == 2
    assert "openai/codex" in capsys.readouterr().err


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


def test_workflow_new_dispatches_to_the_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, NewWorkflowCommand] = {}

    class FakeUseCase(NewWorkflow):
        def execute(self, command: NewWorkflowCommand) -> int:
            seen["command"] = command
            return 0

    monkeypatch.setattr(app, "build_new_workflow", lambda: FakeUseCase())
    assert app.main(["workflow", "new", "doc-review"]) == 0
    assert seen["command"] == NewWorkflowCommand(name="doc-review", client="claude")


def test_workflow_new_reports_errors_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingUseCase(NewWorkflow):
        def execute(self, command: NewWorkflowCommand) -> int:
            raise WorkflowExistsError("workflow already exists: 'doc-review'")

    monkeypatch.setattr(app, "build_new_workflow", lambda: FailingUseCase())
    assert app.main(["workflow", "new", "doc-review"]) == 2
    assert "already exists" in capsys.readouterr().out


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
        def execute(self, command: StartJobCommand) -> int:
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
