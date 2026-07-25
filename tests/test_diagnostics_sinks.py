# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the diagnostics sinks behind ``DiagnosticsPort``."""

from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.diagnostics import levels
from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnostics
from generic_ml_wrapper.adapter.outbound.diagnostics.rolling_file_diagnostics import (
    RollingFileDiagnostics,
)
from generic_ml_wrapper.adapter.outbound.diagnostics.stderr_diagnostics import StderrDiagnostics
from generic_ml_wrapper.adapter.outbound.diagnostics.tee_diagnostics import TeeDiagnostics
from generic_ml_wrapper.application.wiring.composition import build_diagnostics


def _raise(error: BaseException) -> None:
    raise error


def _caught(error: BaseException) -> BaseException:
    """Return *error* after raising it, so it carries a real traceback."""
    try:
        _raise(error)
    except BaseException as raised:  # noqa: BLE001
        return raised
    return error


def _boom() -> BaseException:
    """Return a caught ValueError carrying a traceback."""
    return _caught(ValueError("upstream said no"))


# ---------------------------------------------------------------------------
# levels
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["debug", "info", "warning", "error"])
def test_known_levels_resolve_to_themselves(name: str) -> None:
    assert levels.resolve(name) == name


@pytest.mark.parametrize("bad", ["bogus", "", None, "WARN"])
def test_an_unknown_level_falls_back_rather_than_raising(bad: str | None) -> None:
    # Logging configuration must never be the thing that stops a run.
    assert levels.resolve(bad) == levels.DEFAULT


def test_levels_are_case_insensitive() -> None:
    assert levels.resolve("DEBUG") == "debug"


# ---------------------------------------------------------------------------
# RollingFileDiagnostics
# ---------------------------------------------------------------------------


def test_a_record_is_written_to_the_file(tmp_path: Path) -> None:
    target = tmp_path / "logs" / "gmlw.log"
    RollingFileDiagnostics(target, level="debug").warning("relay failed", client="claude")
    written = target.read_text(encoding="utf-8")
    assert "WARNING" in written
    assert "relay failed" in written
    assert "client=claude" in written


def test_the_parent_directory_is_created_on_demand(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "gmlw.log"
    RollingFileDiagnostics(target, level="info").info("hello")
    assert target.exists()


def test_records_below_the_threshold_are_dropped(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    sink = RollingFileDiagnostics(target, level="warning")
    sink.info("quiet")
    sink.warning("loud")
    written = target.read_text(encoding="utf-8")
    assert "quiet" not in written
    assert "loud" in written


def test_a_traceback_is_preserved_in_the_file(tmp_path: Path) -> None:
    # The whole point of the file sink: the traceback that used to land on the user's
    # screen (uncopyable, unlogged) is kept somewhere it can be read afterwards.
    target = tmp_path / "gmlw.log"
    RollingFileDiagnostics(target, level="error").error("gateway crashed", exc=_boom())
    written = target.read_text(encoding="utf-8")
    assert "gateway crashed" in written
    assert "ValueError: upstream said no" in written
    assert "Traceback (most recent call last)" in written


def test_the_file_rolls_at_the_size_cap(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    sink = RollingFileDiagnostics(target, level="debug", max_bytes=200, backup_count=2)
    for index in range(40):
        sink.warning(f"message number {index} padded out to force a rollover")
    sink.close()
    assert target.exists()
    assert (tmp_path / "gmlw.log.1").exists(), "the file should have rolled"
    # Rotation is bounded: backup_count backups, never an unbounded pile.
    assert not (tmp_path / "gmlw.log.3").exists()


def test_appends_across_sinks_rather_than_truncating(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    first = RollingFileDiagnostics(target, level="info")
    first.info("from the first run")
    first.close()
    second = RollingFileDiagnostics(target, level="info")
    second.info("from the second run")
    second.close()
    written = target.read_text(encoding="utf-8")
    assert "from the first run" in written
    assert "from the second run" in written


def test_an_unwritable_destination_never_raises(tmp_path: Path) -> None:
    # The never-raises contract: a diagnostics failure must not break the run it was
    # only observing. A path whose parent is a *file* cannot be created.
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    sink = RollingFileDiagnostics(blocker / "gmlw.log", level="debug")
    sink.warning("this cannot be written anywhere")
    sink.error("nor can this", exc=_boom())


def test_close_is_idempotent_and_the_sink_survives_it(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    sink = RollingFileDiagnostics(target, level="info")
    sink.info("before")
    sink.close()
    sink.close()
    sink.info("after")
    sink.close()
    assert "after" in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Scrubbing — applied in the sink, so no call site has to remember
# ---------------------------------------------------------------------------


def test_a_sensitive_key_is_redacted_whatever_its_value(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    RollingFileDiagnostics(target, level="info").info("auth", token="short")  # noqa: S106
    written = target.read_text(encoding="utf-8")
    assert "short" not in written
    assert "token=[redacted]" in written


def test_an_api_key_in_the_message_is_scrubbed(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    secret = "sk-ant-api03-" + "A1b2C3d4E5f6G7h8" * 2  # pragma: allowlist secret
    RollingFileDiagnostics(target, level="info").info(f"calling with {secret}")
    written = target.read_text(encoding="utf-8")
    assert secret not in written
    assert "[secret]" in written


def test_an_email_address_is_scrubbed(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    RollingFileDiagnostics(target, level="info").info("user someone@example.com signed in")
    written = target.read_text(encoding="utf-8")
    assert "someone@example.com" not in written
    assert "[email]" in written


def test_a_secret_nested_in_a_dict_value_is_scrubbed(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    headers = {"password": "hunter2"}  # pragma: allowlist secret
    RollingFileDiagnostics(target, level="info").info("headers", meta=headers)
    written = target.read_text(encoding="utf-8")
    assert "hunter2" not in written


def test_a_secret_in_a_traceback_is_scrubbed(tmp_path: Path) -> None:
    # Exception messages quote the thing that failed, which is where credentials leak.
    target = tmp_path / "gmlw.log"
    error = _caught(RuntimeError("refused for Bearer abcdefghijklmnop"))
    RollingFileDiagnostics(target, level="error").error("upstream", exc=error)
    written = target.read_text(encoding="utf-8")
    assert "abcdefghijklmnop" not in written
    assert "[token]" in written


def test_file_paths_in_a_traceback_survive_scrubbing(tmp_path: Path) -> None:
    # Regression: an entropy rule that treats "/" as a secret-ish character eats every
    # long path, so a preserved traceback reads `File "[secret].py"` and is worthless.
    # A traceback is mostly paths — the scrubber has to leave them alone.
    target = tmp_path / "gmlw.log"
    RollingFileDiagnostics(target, level="error").error("crashed", exc=_boom())
    written = target.read_text(encoding="utf-8")
    assert "test_diagnostics_sinks.py" in written
    assert "[secret]" not in written


def test_session_ids_survive_scrubbing(tmp_path: Path) -> None:
    # Over-redaction is its own bug: a log that has eaten its identifiers is useless.
    target = tmp_path / "gmlw.log"
    digest = "a3f5" * 16  # bare lowercase hex, exactly like a content hash
    RollingFileDiagnostics(target, level="info").info("recorded", session=digest)
    assert digest in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Null and Tee
# ---------------------------------------------------------------------------


def test_the_null_sink_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sink = NullDiagnostics()
    sink.debug("a")
    sink.info("b")
    sink.warning("c")
    sink.error("d", exc=_boom())
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert list(tmp_path.iterdir()) == []


def test_the_tee_feeds_every_sink(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "gmlw.log"
    tee = TeeDiagnostics(
        RollingFileDiagnostics(target, level="debug"),
        StderrDiagnostics(level="debug"),
    )
    tee.debug("d")
    tee.info("i")
    tee.warning("w")
    tee.error("e", exc=_boom())
    written = target.read_text(encoding="utf-8")
    err = capsys.readouterr().err
    for message in ("d", "i", "w", "e"):
        assert message in written
        assert message in err


def test_an_empty_tee_is_a_null_sink() -> None:
    TeeDiagnostics().warning("nowhere to go")


def test_a_secret_inside_a_list_value_is_scrubbed(tmp_path: Path) -> None:
    target = tmp_path / "gmlw.log"
    secret = "sk-ant-api03-" + "A1b2C3d4E5f6G7h8" * 2  # pragma: allowlist secret
    RollingFileDiagnostics(target, level="info").info("headers", values=["safe", secret])
    written = target.read_text(encoding="utf-8")
    assert secret not in written
    assert "safe" in written


def test_the_stderr_sink_never_raises_on_a_broken_stream() -> None:
    class _Broken:
        def write(self, text: str) -> int:
            raise OSError("stream is gone")

        def flush(self) -> None:
            raise OSError("stream is gone")

    # A closed or redirected-into-nothing stderr must not take the run down with it.
    StderrDiagnostics(level="debug", stream=_Broken()).warning("into a broken pipe")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_diagnostics — the wiring policy
# ---------------------------------------------------------------------------


def test_the_statusline_gets_a_silent_sink() -> None:
    # It renders into another program's prompt, from a short-lived subprocess, many
    # times a session: it must neither write a byte nor race for the rolling file.
    assert isinstance(build_diagnostics(quiet=True), NullDiagnostics)


def test_a_handover_command_writes_to_the_file_only() -> None:
    # Issue #59: with a client owning the screen, stderr is not ours to write to.
    sink = build_diagnostics(to_stderr=False)
    assert isinstance(sink, RollingFileDiagnostics)


def test_a_utility_command_tees_the_file_and_stderr() -> None:
    sink = build_diagnostics(to_stderr=True)
    assert isinstance(sink, TeeDiagnostics)


def test_the_file_sink_is_dropped_when_the_config_disables_it(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("[logging]\nto_file = false\n", encoding="utf-8")
    assert isinstance(build_diagnostics(to_stderr=True, path=config_file), StderrDiagnostics)


def test_disabling_both_destinations_yields_a_null_sink(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("[logging]\nto_file = false\n", encoding="utf-8")
    assert isinstance(
        build_diagnostics(to_stderr=False, path=config_file),
        NullDiagnostics,
    )
