# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the WhatsNew use case and the packaged changelog it reads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.update.packaged_changelog import PackagedChangelog
from generic_ml_wrapper.application.port.outbound.release_notes import ReleaseNotesPort
from generic_ml_wrapper.application.usecase.whats_new import WhatsNewUseCase

_CHANGELOG = """# Changelog

## [0.13.0] - 2026-11-01
- New.

## [0.12.1] - 2026-10-11
- Fixed.

## [0.12.0] - 2026-10-10
- Old.
"""


class _Source(ReleaseNotesPort):
    def __init__(self, text: str | None = _CHANGELOG) -> None:
        self._text = text

    def read(self) -> str | None:
        return self._text


def _use_case(
    state: Path, current: str = "0.13.0", text: str | None = _CHANGELOG
) -> WhatsNewUseCase:
    return WhatsNewUseCase(source=_Source(text), current_version=current, state_path=state)


def _seen(state: Path, version: str) -> None:
    state.write_text(json.dumps({"seen": version}), encoding="utf-8")


def test_all_reads_every_release(tmp_path: Path) -> None:
    notes = _use_case(tmp_path / "s.json").all()
    assert [n.version for n in notes] == ["0.13.0", "0.12.1", "0.12.0"]


def test_without_a_changelog_there_is_nothing_to_show(tmp_path: Path) -> None:
    assert _use_case(tmp_path / "s.json", text=None).all() == ()


def test_the_first_call_shows_nothing_and_starts_the_record(tmp_path: Path) -> None:
    state = tmp_path / "state" / "whats-new.json"
    assert _use_case(state).take_unseen() == ()
    assert json.loads(state.read_text(encoding="utf-8")) == {"seen": "0.13.0"}


def test_after_an_upgrade_the_releases_since_show_once(tmp_path: Path) -> None:
    state = tmp_path / "whats-new.json"
    _seen(state, "0.12.0")
    first = _use_case(state).take_unseen()
    assert [n.version for n in first] == ["0.13.0", "0.12.1"]
    assert _use_case(state).take_unseen() == ()  # shown once


def test_a_downgrade_shows_nothing_and_moves_the_record(tmp_path: Path) -> None:
    state = tmp_path / "whats-new.json"
    _seen(state, "0.13.0")
    assert _use_case(state, current="0.12.1").take_unseen() == ()
    assert json.loads(state.read_text(encoding="utf-8")) == {"seen": "0.12.1"}


@pytest.mark.parametrize("text", ["not json", "[]", '{"seen": 3}', '{"other": "x"}'])
def test_an_unreadable_record_counts_as_none(tmp_path: Path, text: str) -> None:
    state = tmp_path / "whats-new.json"
    state.write_text(text, encoding="utf-8")
    assert _use_case(state).take_unseen() == ()
    assert json.loads(state.read_text(encoding="utf-8")) == {"seen": "0.13.0"}


def test_a_record_that_cannot_be_written_is_not_fatal(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    assert _use_case(blocker / "whats-new.json").take_unseen() == ()  # parent is a file


def test_the_packaged_changelog_reads_the_first_place_holding_one(tmp_path: Path) -> None:
    present = tmp_path / "CHANGELOG.md"
    present.write_text("# Changelog\n", encoding="utf-8")
    missing = tmp_path / "missing.md"
    assert PackagedChangelog([missing, present]).read() == "# Changelog\n"
    assert PackagedChangelog([missing]).read() is None


def test_an_undecodable_changelog_is_skipped(tmp_path: Path) -> None:
    broken = tmp_path / "CHANGELOG.md"
    broken.write_bytes(b"\xff\xfe\xfa")
    assert PackagedChangelog([broken]).read() is None


def test_a_checkout_reads_the_repository_changelog() -> None:
    text = PackagedChangelog().read()
    assert text is not None
    assert text.startswith("# Changelog")
