# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for an installation's upgrade command and an update check's verdict."""

from __future__ import annotations

import pytest

from generic_ml_wrapper.application.domain.model.installation import (
    Installation,
    InstallManager,
    InstallSource,
)
from generic_ml_wrapper.application.domain.model.update_check import UpdateCheck, is_newer

_REPO = "https://github.com/danielslobozian/generic-ml-wrapper"
_PYTHON = "/home/u/.venv/bin/python"


@pytest.mark.parametrize(
    ("manager", "expected"),
    [
        (InstallManager.UV_TOOL, "uv tool upgrade generic-ml-wrapper"),
        (InstallManager.PIPX, "pipx upgrade generic-ml-wrapper"),
        (
            InstallManager.UV_PIP,
            f"uv pip install --python {_PYTHON} --upgrade generic-ml-wrapper",
        ),
        (InstallManager.PIP, f"{_PYTHON} -m pip install --upgrade generic-ml-wrapper"),
    ],
)
def test_a_release_from_pypi_upgrades_in_place(manager: InstallManager, expected: str) -> None:
    installation = Installation(InstallSource.INDEX, manager, None, _PYTHON)
    assert installation.upgrade_command("0.13.0") == expected


@pytest.mark.parametrize(
    ("manager", "expected"),
    [
        (
            InstallManager.UV_TOOL,
            f"uv tool install --force 'generic-ml-wrapper @ git+{_REPO}@v0.13.0'",
        ),
        (InstallManager.PIPX, f"pipx install --force git+{_REPO}@v0.13.0"),
        (
            InstallManager.UV_PIP,
            f"uv pip install --python {_PYTHON} --upgrade "
            f"'generic-ml-wrapper @ git+{_REPO}@v0.13.0'",
        ),
        (
            InstallManager.PIP,
            f"{_PYTHON} -m pip install --upgrade 'generic-ml-wrapper @ git+{_REPO}@v0.13.0'",
        ),
    ],
)
def test_a_git_install_is_reinstalled_at_the_release_tag(
    manager: InstallManager, expected: str
) -> None:
    installation = Installation(InstallSource.GIT, manager, _REPO, _PYTHON)
    assert installation.upgrade_command("0.13.0") == expected


def test_a_source_install_has_no_command() -> None:
    installation = Installation(InstallSource.SOURCE, InstallManager.UV_PIP, "/src/gmlw")
    assert installation.upgrade_command("0.13.0") is None


def test_an_interpreter_path_with_a_space_is_quoted() -> None:
    installation = Installation(InstallSource.INDEX, InstallManager.PIP, None, "/My Env/python")
    assert installation.upgrade_command("1.0.0") == (
        "'/My Env/python' -m pip install --upgrade generic-ml-wrapper"
    )


@pytest.mark.parametrize(
    ("latest", "current", "expected"),
    [
        ("0.13.0", "0.12.1", True),
        ("0.12.10", "0.12.9", True),  # compared as numbers, not text
        ("0.12.1", "0.12.1", False),
        ("0.12.0", "0.12.1", False),
        ("0.13.0rc1", "0.12.1", False),  # unreadable: never newer
    ],
)
def test_is_newer(latest: str, current: str, *, expected: bool) -> None:
    assert is_newer(latest, current) is expected


_PYPI = Installation(InstallSource.INDEX, InstallManager.UV_TOOL)


def test_a_newer_release_comes_with_its_command() -> None:
    check = UpdateCheck("0.12.1", "0.13.0", _PYPI)
    assert check.newer
    assert check.command == "uv tool upgrade generic-ml-wrapper"


@pytest.mark.parametrize("latest", ["0.12.1", None])
def test_no_newer_release_no_command(latest: str | None) -> None:
    check = UpdateCheck("0.12.1", latest, _PYPI)
    assert not check.newer
    assert check.command is None
