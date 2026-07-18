# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the built-in callers and the default provider."""

import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from generic_ml_wrapper.adapter.outbound.caller import (
    claude_cli_caller,
    cursor_cli_caller,
    vibe_cli_caller,
)
from generic_ml_wrapper.adapter.outbound.caller.claude_cli_caller import BINARY, ClaudeCliCaller
from generic_ml_wrapper.adapter.outbound.caller.codex_cli_caller import CodexCliCaller
from generic_ml_wrapper.adapter.outbound.caller.cursor_cli_caller import CursorCliCaller
from generic_ml_wrapper.adapter.outbound.caller.default_provider import (
    DefaultCliCallerProvider,
    UnsupportedClientError,
)
from generic_ml_wrapper.adapter.outbound.caller.vibe_cli_caller import VibeCliCaller
from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.plugin_source import PluginSourcePort


class _BareCaller(CliCaller):
    def start_client(self) -> int:
        return 0


class _FakeMetering(PerTurnMeteringPort):
    def record(self, job: str, turn: TurnUsage) -> None:
        pass

    def turns_for_job(self, job: str) -> list[TurnUsage]:
        return []


_METERING = _FakeMetering()


def _claude(run: RunContext) -> ClaudeCliCaller:
    return ClaudeCliCaller(run, _METERING)


def _codex(run: RunContext) -> CodexCliCaller:
    return CodexCliCaller(run, _METERING)


def _vibe(run: RunContext) -> VibeCliCaller:
    return VibeCliCaller(run, _METERING)


def _run(  # noqa: PLR0913
    *,
    resume: bool,
    uuid: str | None,
    context: str | None = None,
    kickoff: str | None = None,
    cwd: str | None = None,
    env: tuple[tuple[str, str], ...] = (),
) -> RunContext:
    return RunContext(
        "JOB-1",
        "JOB-1_001",
        "claude",
        uuid,
        resume,
        cwd=cwd,
        context=context,
        kickoff=kickoff,
        env=env,
    )


def test_command_for_new_session_with_uuid() -> None:
    caller = _claude(_run(resume=False, uuid="u-1"))
    assert caller.command() == [BINARY, "-n", "JOB-1_001", "--session-id", "u-1"]


def test_command_for_new_session_without_uuid() -> None:
    caller = _claude(_run(resume=False, uuid=None))
    assert caller.command() == [BINARY, "-n", "JOB-1_001"]


def test_command_for_resume_prefers_uuid() -> None:
    caller = _claude(_run(resume=True, uuid="u-1"))
    assert caller.command() == [BINARY, "--resume", "u-1"]


def test_command_appends_context_and_kickoff() -> None:
    caller = _claude(_run(resume=False, uuid=None, kickoff="go"))
    assert caller.command("/tmp/ctx.md") == [
        BINARY,
        "-n",
        "JOB-1_001",
        "--append-system-prompt-file",
        "/tmp/ctx.md",
        "go",
    ]


def test_start_client_runs_the_command_and_exports_env(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(
        argv: list[str], *, check: bool, cwd: str | None, env: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        seen["argv"] = argv
        seen["cwd"] = cwd
        seen["env"] = env
        assert check is False
        return subprocess.CompletedProcess(argv, returncode=7)

    monkeypatch.setattr(claude_cli_caller.subprocess, "run", fake_run)
    caller = _claude(_run(resume=False, uuid=None, cwd="/work"))
    assert caller.start_client() == 7
    assert seen["argv"] == [BINARY, "-n", "JOB-1_001"]
    assert seen["cwd"] == "/work"
    env = cast("dict[str, str]", seen["env"])
    assert env["GMLW_JOB"] == "JOB-1"
    assert env["GMLW_SESSION"] == "JOB-1_001"
    assert env["GMLW_CLIENT"] == "claude"


def test_start_client_exports_run_env(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(
        argv: list[str], *, check: bool, cwd: str | None, env: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        seen["env"] = env
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(claude_cli_caller.subprocess, "run", fake_run)
    caller = _claude(_run(resume=False, uuid=None, env=(("EXTRA_VAR", "v1"),)))
    caller.start_client()
    assert cast("dict[str, str]", seen["env"])["EXTRA_VAR"] == "v1"


def test_start_client_injects_context_via_a_durable_file(monkeypatch: pytest.MonkeyPatch) -> None:
    written: dict[str, str] = {}

    def fake_run(
        argv: list[str], *, check: bool, cwd: str | None, env: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        assert check is False
        assert cwd is None
        flag_index = argv.index("--append-system-prompt-file")
        written["path"] = argv[flag_index + 1]
        written["context"] = Path(argv[flag_index + 1]).read_text(encoding="utf-8")
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(claude_cli_caller.subprocess, "run", fake_run)
    caller = _claude(_run(resume=False, uuid=None, context="MY CONTEXT"))
    assert caller.start_client() == 0
    assert written["context"] == "MY CONTEXT"
    assert Path(written["path"]).exists()  # durable: the context file survives the run


def test_metering_installs_and_restores_the_status_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text('{"statusLine": "MINE", "other": 1}', encoding="utf-8")
    monkeypatch.setattr(claude_cli_caller, "_SETTINGS", settings)

    caller = _claude(_run(resume=False, uuid=None))
    caller.start_metering()
    installed = json.loads(settings.read_text(encoding="utf-8"))
    assert installed["statusLine"]["command"] == "gmlw statusline"
    assert installed["other"] == 1  # untouched

    caller.end_metering()
    restored = json.loads(settings.read_text(encoding="utf-8"))
    assert restored["statusLine"] == "MINE"  # previous value restored


def test_metering_removes_status_line_when_there_was_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"  # does not exist yet
    monkeypatch.setattr(claude_cli_caller, "_SETTINGS", settings)

    caller = _claude(_run(resume=False, uuid=None))
    caller.start_metering()
    assert "gmlw statusline" in settings.read_text(encoding="utf-8")
    caller.end_metering()
    assert "statusLine" not in json.loads(settings.read_text(encoding="utf-8"))


def test_claude_can_deliver_statusline() -> None:
    assert _claude(_run(resume=False, uuid=None)).can_deliver_statusline() is True


def test_base_caller_cannot_deliver_statusline_by_default() -> None:
    assert _BareCaller(_run(resume=False, uuid=None)).can_deliver_statusline() is False


def test_claude_meters_per_call_while_the_base_caller_does_not() -> None:
    # Claude now routes through the relay, so it records per-turn usage; the bare
    # base caller does not until a caller opts in.
    assert _BareCaller(_run(resume=False, uuid=None)).can_meter_per_call() is False
    assert _claude(_run(resume=False, uuid=None)).can_meter_per_call() is True


def test_metering_is_skipped_when_statusline_undeliverable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text('{"statusLine": "MINE"}', encoding="utf-8")
    monkeypatch.setattr(claude_cli_caller, "_SETTINGS", settings)

    def _cannot_deliver(_self: object) -> bool:
        return False

    monkeypatch.setattr(ClaudeCliCaller, "can_deliver_statusline", _cannot_deliver)

    caller = _claude(_run(resume=False, uuid=None))
    caller.start_metering()
    assert json.loads(settings.read_text(encoding="utf-8"))["statusLine"] == "MINE"  # untouched
    caller.end_metering()  # no snapshot → safe no-op
    assert json.loads(settings.read_text(encoding="utf-8"))["statusLine"] == "MINE"


def test_claude_metering_routes_through_the_relay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(claude_cli_caller, "_SETTINGS", settings)
    seen: dict[str, object] = {}

    def fake_run(
        argv: list[str], *, check: bool, cwd: str | None, env: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        seen["env"] = env
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(claude_cli_caller.subprocess, "run", fake_run)
    caller = _claude(_run(resume=False, uuid=None))
    assert caller.can_meter_per_call() is True
    caller.start_metering()
    try:
        # the status line coexists with the relay while metering is active
        assert "gmlw statusline" in settings.read_text(encoding="utf-8")
        caller.start_client()
    finally:
        caller.end_metering()

    env = cast("dict[str, str]", seen["env"])
    assert env["ANTHROPIC_BASE_URL"].startswith("http://127.0.0.1:")


def test_provider_returns_claude_caller() -> None:
    provider = DefaultCliCallerProvider(metering=_FakeMetering())
    assert isinstance(provider.for_run(_run(resume=False, uuid=None)), ClaudeCliCaller)


def test_provider_rejects_unknown_client() -> None:
    run = RunContext("JOB-1", "JOB-1_001", "gemini", None, False)
    with pytest.raises(UnsupportedClientError):
        DefaultCliCallerProvider(metering=_FakeMetering()).for_run(run)


def test_provider_uses_a_config_override() -> None:
    # An override target is an external caller constructed with just the run.
    spec = "generic_ml_wrapper.adapter.outbound.caller.cursor_cli_caller:CursorCliCaller"
    provider = DefaultCliCallerProvider({"gemini": spec}, metering=_FakeMetering())
    run = RunContext("JOB-1", "JOB-1_001", "gemini", None, False)
    assert isinstance(provider.for_run(run), CursorCliCaller)


def test_provider_resolves_a_plugin_id_override() -> None:
    # A bare override value is a plugin id, resolved to a loadable spec by the source.
    spec = "generic_ml_wrapper.adapter.outbound.caller.cursor_cli_caller:CursorCliCaller"

    class _Plugins(PluginSourcePort):
        def available(self) -> list[Plugin]:
            return []

        def resolve_caller(self, reference: str) -> str:
            return spec if reference == "my-cursor" else reference

        def resolve_hook(self, reference: str) -> str:
            return reference

    provider = DefaultCliCallerProvider(
        {"gemini": "my-cursor"}, metering=_FakeMetering(), plugins=_Plugins()
    )
    run = RunContext("JOB-1", "JOB-1_001", "gemini", None, False)
    assert isinstance(provider.for_run(run), CursorCliCaller)


# ── cursor-agent (light) ──
def _cursor_run(
    *, resume: bool, context: str | None = None, kickoff: str | None = None
) -> RunContext:
    return RunContext(
        "JOB-1", "JOB-1_001", "cursor", None, resume, context=context, kickoff=kickoff
    )


def test_cursor_command_resumes_by_session_name() -> None:
    caller = CursorCliCaller(_cursor_run(resume=False))
    assert caller.command() == ["cursor-agent", "--resume", "JOB-1_001"]
    assert caller.command("go") == ["cursor-agent", "--resume", "JOB-1_001", "go"]


def test_cursor_delivers_statusline_but_does_not_meter() -> None:
    caller = CursorCliCaller(_cursor_run(resume=False))
    assert caller.can_deliver_statusline() is True
    assert caller.can_meter_per_call() is False


def test_cursor_metering_installs_and_restores_status_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "cli-config.json"
    config.write_text('{"statusLine": "MINE", "network": {}}', encoding="utf-8")
    monkeypatch.setattr(cursor_cli_caller, "_CONFIG", config)

    caller = CursorCliCaller(_cursor_run(resume=False))
    caller.start_metering()
    installed = json.loads(config.read_text(encoding="utf-8"))
    assert installed["statusLine"]["command"] == "gmlw statusline"
    assert installed["network"] == {}  # untouched
    caller.end_metering()
    assert json.loads(config.read_text(encoding="utf-8"))["statusLine"] == "MINE"


def test_cursor_injects_context_via_a_read_this_file_opening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def fake_run(
        argv: list[str], *, check: bool, cwd: str | None, env: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        opening = argv[-1]
        path = next(token for token in opening.split() if token.endswith(".md"))
        seen["context"] = Path(path).read_text(encoding="utf-8")
        seen["client"] = env["GMLW_CLIENT"]
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(cursor_cli_caller.subprocess, "run", fake_run)
    assert CursorCliCaller(_cursor_run(resume=False, context="MY CONTEXT")).start_client() == 0
    assert seen["context"] == "MY CONTEXT"
    assert seen["client"] == "cursor"


def test_provider_returns_cursor_caller() -> None:
    provider = DefaultCliCallerProvider(metering=_FakeMetering())
    run = RunContext("JOB-1", "JOB-1_001", "cursor", None, False)
    assert isinstance(provider.for_run(run), CursorCliCaller)


# ── codex ──
def _codex_run(*, context: str | None = None, kickoff: str | None = None) -> RunContext:
    return RunContext("JOB-1", "JOB-1_001", "codex", None, False, context=context, kickoff=kickoff)


def test_codex_bare_command_is_codex_plus_opening() -> None:
    caller = _codex(_codex_run())  # before start_metering: no relay, plain command
    assert caller.command() == ["codex"]
    assert caller.command("go") == ["codex", "go"]


def test_codex_meters_but_delivers_no_statusline() -> None:
    caller = _codex(_codex_run())
    assert caller.can_deliver_statusline() is False
    assert caller.can_meter_per_call() is True


def test_codex_and_vibe_cannot_resume_while_others_can() -> None:
    # Resume is the default (claude/cursor support it); codex and vibe opt out
    # because neither lets the wrapper set a session id at launch.
    assert _BareCaller(_run(resume=False, uuid=None)).can_resume() is True
    assert _claude(_run(resume=False, uuid=None)).can_resume() is True
    assert CursorCliCaller(_cursor_run(resume=False)).can_resume() is True
    assert _codex(_codex_run()).can_resume() is False
    assert _vibe(_vibe_run()).can_resume() is False


def test_codex_metering_points_provider_at_the_relay() -> None:
    caller = _codex(_codex_run())
    assert caller.can_meter_per_call() is True
    caller.start_metering()
    try:
        argv = caller.command("hi")
    finally:
        caller.end_metering()

    assert argv[0] == "codex"
    assert 'model_provider="gml"' in argv
    base_flag = next(a for a in argv if a.startswith("model_providers.gml.base_url="))
    assert "http://127.0.0.1:" in base_flag
    assert base_flag.endswith('/v1"')
    assert argv[-1] == "hi"


def test_provider_returns_codex_caller() -> None:
    provider = DefaultCliCallerProvider(metering=_FakeMetering())
    run = RunContext("JOB-1", "JOB-1_001", "codex", None, False)
    assert type(provider.for_run(run)) is CodexCliCaller


# ── vibe (Mistral CLI) ──
_VIBE_SAMPLE = """\
active_model = "mistral-medium-3.5"

[[providers]]
name = "mistral"
api_base = "https://api.mistral.ai/v1"
api_key_env_var = "MISTRAL_API_KEY"
api_style = "openai"
backend = "mistral"

[[providers]]
name = "tts"
api_base = "https://api.mistral.ai"

[[models]]
name = "mistral-vibe-cli-latest"
provider = "mistral"
alias = "mistral-medium-3.5"
"""


def _vibe_run(*, context: str | None = None, kickoff: str | None = None) -> RunContext:
    return RunContext("JOB-1", "JOB-1_001", "vibe", None, False, context=context, kickoff=kickoff)


def test_vibe_bare_command_is_vibe_plus_opening() -> None:
    caller = _vibe(_vibe_run())  # before start_metering: no relay, plain command
    assert caller.command() == ["vibe"]
    assert caller.command("go") == ["vibe", "go"]


def test_vibe_meters_but_neither_resumes_nor_delivers_statusline() -> None:
    caller = _vibe(_vibe_run())
    assert caller.can_resume() is False
    assert caller.can_deliver_statusline() is False
    assert caller.can_meter_per_call() is True


def test_vibe_injects_context_via_a_read_this_file_opening(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def fake_run(
        argv: list[str], *, check: bool, cwd: str | None, env: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        opening = argv[-1]
        path = next(token for token in opening.split() if token.endswith(".md"))
        seen["context"] = Path(path).read_text(encoding="utf-8")
        seen["client"] = env["GMLW_CLIENT"]
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(vibe_cli_caller.subprocess, "run", fake_run)
    assert _vibe(_vibe_run(context="MY CONTEXT")).start_client() == 0
    assert seen["context"] == "MY CONTEXT"
    assert seen["client"] == "vibe"


def test_vibe_metering_routes_through_a_relay_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(_VIBE_SAMPLE, encoding="utf-8")
    monkeypatch.setattr(vibe_cli_caller, "_VIBE_CONFIG", config)

    seen: dict[str, str] = {}

    def fake_run(
        argv: list[str], *, check: bool, cwd: str | None, env: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        seen["argv"] = " ".join(argv)
        seen["config"] = (Path(env["VIBE_HOME"]) / "config.toml").read_text(encoding="utf-8")
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(vibe_cli_caller.subprocess, "run", fake_run)

    caller = _vibe(_vibe_run(kickoff="hi"))
    assert caller.can_meter_per_call() is True
    caller.start_metering()
    try:
        assert caller.start_client() == 0
    finally:
        caller.end_metering()

    assert "--trust" in seen["argv"].split()
    assert seen["argv"].endswith("hi")
    # the mistral provider's api_base now points at the local relay, path preserved;
    # the tts provider (no /v1) is left alone
    assert "https://api.mistral.ai/v1" not in seen["config"]
    assert "http://127.0.0.1:" in seen["config"]
    assert 'api_base = "https://api.mistral.ai"' in seen["config"]  # tts untouched


def test_vibe_metering_falls_back_to_unmetered_without_a_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(vibe_cli_caller, "_VIBE_CONFIG", tmp_path / "missing.toml")
    caller = _vibe(_vibe_run())
    caller.start_metering()
    try:
        assert caller.command("hi") == ["vibe", "hi"]  # no relay, no --trust
        assert caller._extra_env() == {}  # no VIBE_HOME injected
    finally:
        caller.end_metering()


def test_provider_returns_vibe_caller() -> None:
    provider = DefaultCliCallerProvider(metering=_FakeMetering())
    run = RunContext("JOB-1", "JOB-1_001", "vibe", None, False)
    assert type(provider.for_run(run)) is VibeCliCaller
