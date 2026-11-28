# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for running an attachment's pre-flight script with gmlw's own Python."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.attachment.subprocess_pre_flight_runner import (
    SubprocessPreFlightRunner,
)

if TYPE_CHECKING:
    from pathlib import Path

_REPORT = """\
import json, os, pathlib, sys
pathlib.Path("seen.json").write_text(json.dumps({
    "cwd": os.getcwd(),
    "job": os.environ.get("GMLW_JOB"),
    "stdin": sys.stdin.read(),
}))
"""


def test_the_script_runs_in_the_folder_with_the_env_and_no_input(tmp_path: Path) -> None:
    script = tmp_path / "attachment" / "pre_flight.py"
    script.parent.mkdir()
    script.write_text(_REPORT)
    work = tmp_path / "work"
    work.mkdir()

    code = SubprocessPreFlightRunner().run(script, str(work), {"GMLW_JOB": "JOB-1"})

    assert code == 0
    seen = json.loads((work / "seen.json").read_text())
    assert seen == {"cwd": str(work), "job": "JOB-1", "stdin": ""}


def test_the_script_exit_code_is_returned(tmp_path: Path) -> None:
    script = tmp_path / "pre_flight.py"
    script.write_text("raise SystemExit(4)\n")

    assert SubprocessPreFlightRunner().run(script, str(tmp_path), {}) == 4


def test_a_folder_that_cannot_be_entered_is_a_failure(tmp_path: Path) -> None:
    script = tmp_path / "pre_flight.py"
    script.write_text("pass\n")

    assert SubprocessPreFlightRunner().run(script, str(tmp_path / "missing"), {}) == 1
