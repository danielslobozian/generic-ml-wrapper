# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for loading an external CliCaller from a spec."""

from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.caller.claude_cli_caller import ClaudeCliCaller
from generic_ml_wrapper.adapter.outbound.caller.loader import CallerLoadError, load_caller_class

_CLAUDE_SPEC = "generic_ml_wrapper.adapter.outbound.caller.claude_cli_caller:ClaudeCliCaller"


def test_loads_a_class_from_a_module_spec() -> None:
    assert load_caller_class(_CLAUDE_SPEC) is ClaudeCliCaller


def test_loads_a_class_from_a_file_spec(tmp_path: Path) -> None:
    module = tmp_path / "my_caller.py"
    module.write_text(
        "from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller\n"
        "class MyCaller(CliCaller):\n"
        "    def start_client(self) -> int:\n"
        "        return 0\n",
        encoding="utf-8",
    )
    loaded = load_caller_class(f"{module}:MyCaller")
    assert loaded.__name__ == "MyCaller"


@pytest.mark.parametrize("spec", ["no-colon", "module:", ":Class"])
def test_malformed_spec_is_rejected(spec: str) -> None:
    with pytest.raises(CallerLoadError):
        load_caller_class(spec)


def test_missing_module_is_rejected() -> None:
    with pytest.raises(CallerLoadError):
        load_caller_class("no.such.module:Thing")


def test_non_caller_class_is_rejected() -> None:
    with pytest.raises(CallerLoadError):
        load_caller_class("pathlib:Path")
