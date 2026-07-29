# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for registering a gmlw session name in codex's own session index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.caller import codex_session_index

_UUID = "019f9f6b-9989-7502-82b7-781594cd2d5c"


def _rows(root: Path) -> list[dict[str, object]]:
    index = root / "session_index.jsonl"
    if not index.is_file():
        return []
    return [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line]


def _rollout(root: Path, uuid: str, *, day: str = "2026/07/26") -> Path:
    folder = root / "sessions" / day
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"rollout-2026-07-26T19-14-16-{uuid}.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    return path


# ── home ──
def test_codex_home_follows_the_environment_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "elsewhere"))
    assert codex_session_index.home() == tmp_path / "elsewhere"


def test_codex_home_defaults_to_a_dot_folder_directly_under_the_user_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``.codex`` folder sitting directly in the user's home — on every OS.

    Deliberately asserted as a *shape* rather than as ``Path.home() / ".codex"``. That
    equality would only restate the implementation: it passes by construction, and would
    keep passing on Windows even if this resolved to ``%APPDATA%``.

    Stated as a shape, the CI matrix gives it teeth — the suite runs on windows-latest,
    where an ``%APPDATA%``-style branch would put the folder under ``AppData/Roaming``
    and fail the ``parent`` assertion on the runner that matters.

    What no test here can establish is where codex *itself* looks; that is codex's fact,
    and a green CI is not evidence about it. The evidence is codex's own resolution in
    ``codex-rs/utils/home-dir/src/lib.rs``::

        /// specified by the `CODEX_HOME` environment variable. If not set, defaults to
        /// `~/.codex`.
        None => { let mut p = home_dir()?; p.push(".codex"); }

    ``dirs::home_dir()`` is the user profile on Windows too, so codex's path is uniform
    across platforms and ours must stay uniform with it. If that ever changes upstream,
    this test will not notice — re-read that file, do not trust this suite for it.
    """
    monkeypatch.delenv("CODEX_HOME", raising=False)
    home = codex_session_index.home()
    assert home.name == ".codex"
    assert home.parent == Path.home()


# ── knows ──
def test_a_session_with_a_rollout_is_known(tmp_path: Path) -> None:
    _rollout(tmp_path, _UUID)
    assert codex_session_index.knows(_UUID, root=tmp_path) is True


def test_a_session_without_a_rollout_is_not_known(tmp_path: Path) -> None:
    # The case that matters: codex answers an unknown session by starting a NEW one
    # rather than by failing, so a resume that skipped this check would hand the user an
    # empty session wearing a resumed session's name.
    _rollout(tmp_path, "some-other-session")
    assert codex_session_index.knows(_UUID, root=tmp_path) is False


def test_an_absent_sessions_folder_knows_nothing(tmp_path: Path) -> None:
    assert codex_session_index.knows(_UUID, root=tmp_path) is False


def test_an_empty_uuid_is_never_known(tmp_path: Path) -> None:
    _rollout(tmp_path, _UUID)
    assert codex_session_index.knows("", root=tmp_path) is False


def test_a_rollout_is_found_whatever_day_folder_it_sits_in(tmp_path: Path) -> None:
    _rollout(tmp_path, _UUID, day="2025/01/02")
    assert codex_session_index.knows(_UUID, root=tmp_path) is True


# ── register ──
def test_registering_binds_the_name_to_the_session(tmp_path: Path) -> None:
    assert codex_session_index.register("JOB-1_003", _UUID, root=tmp_path) is True
    rows = _rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["id"] == _UUID
    assert rows[0]["thread_name"] == "JOB-1_003"
    assert rows[0]["updated_at"]


def test_registering_preserves_entries_for_other_sessions(tmp_path: Path) -> None:
    # The index is the user's file and holds names we did not write.
    index = tmp_path / "session_index.jsonl"
    index.write_text(
        json.dumps({"id": "other-id", "thread_name": "their-name", "updated_at": "x"}) + "\n",
        encoding="utf-8",
    )
    codex_session_index.register("JOB-1_003", _UUID, root=tmp_path)
    names = {row["thread_name"] for row in _rows(tmp_path)}
    assert names == {"their-name", "JOB-1_003"}


def test_re_registering_the_same_session_rebinds_rather_than_accumulates(tmp_path: Path) -> None:
    codex_session_index.register("JOB-1_003", _UUID, root=tmp_path)
    codex_session_index.register("JOB-1_003", _UUID, root=tmp_path)
    assert len(_rows(tmp_path)) == 1


def test_a_name_resolves_to_exactly_one_session(tmp_path: Path) -> None:
    # Reusing a name for a different session must move the name, not leave it ambiguous:
    # codex resolves a name to a session, so two rows would make the resume a coin toss.
    codex_session_index.register("JOB-1_003", "old-session", root=tmp_path)
    codex_session_index.register("JOB-1_003", _UUID, root=tmp_path)
    rows = _rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["id"] == _UUID


def test_renaming_a_session_leaves_it_with_one_name(tmp_path: Path) -> None:
    codex_session_index.register("old-name", _UUID, root=tmp_path)
    codex_session_index.register("JOB-1_003", _UUID, root=tmp_path)
    rows = _rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["thread_name"] == "JOB-1_003"


def test_an_unparseable_line_is_dropped_and_the_rest_kept(tmp_path: Path) -> None:
    index = tmp_path / "session_index.jsonl"
    index.write_text(
        "not json\n"
        + json.dumps({"id": "other-id", "thread_name": "their-name", "updated_at": "x"})
        + "\n",
        encoding="utf-8",
    )
    codex_session_index.register("JOB-1_003", _UUID, root=tmp_path)
    rows = _rows(tmp_path)
    assert {row["thread_name"] for row in rows} == {"their-name", "JOB-1_003"}


def test_registering_creates_the_index_when_codex_has_none(tmp_path: Path) -> None:
    fresh = tmp_path / "never-used"
    assert codex_session_index.register("JOB-1_003", _UUID, root=fresh) is True
    assert (fresh / "session_index.jsonl").is_file()


def test_registering_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    codex_session_index.register("JOB-1_003", _UUID, root=tmp_path)
    assert list(tmp_path.glob("*.gmlw-tmp")) == []


def test_a_failed_registration_is_reported_not_raised(tmp_path: Path) -> None:
    # codex's index is the user's file; if it cannot be written, the session still runs.
    blocked = tmp_path / "session_index.jsonl"
    blocked.mkdir()  # a directory where the index should be: every write fails
    assert codex_session_index.register("JOB-1_003", _UUID, root=tmp_path) is False
