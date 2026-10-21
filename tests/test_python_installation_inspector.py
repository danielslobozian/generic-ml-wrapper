# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for reading how gmlw was installed off an environment's packaging metadata."""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.update.python_installation_inspector import (
    PythonInstallationInspector,
)
from generic_ml_wrapper.application.domain.model.installation import (
    Installation,
    InstallManager,
    InstallSource,
)

_REPO = "https://github.com/danielslobozian/generic-ml-wrapper"


def _inspect(
    prefix: Path,
    *,
    direct_url: object = None,
    installer: str | None = None,
    marker: str | None = None,
) -> Installation:
    """Inspect an environment at ``prefix`` holding a gmlw dist-info with these files."""
    dist_info = prefix / "site-packages" / "generic_ml_wrapper-0.12.1.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text("Name: generic-ml-wrapper\nVersion: 0.12.1\n")
    if direct_url is not None:
        text = direct_url if isinstance(direct_url, str) else json.dumps(direct_url)
        (dist_info / "direct_url.json").write_text(text)
    if installer is not None:
        (dist_info / "INSTALLER").write_text(installer)
    if marker is not None:
        (prefix / marker).write_text("")
    found = metadata.PathDistribution(dist_info)
    return PythonInstallationInspector(lambda: found, prefix, "/env/bin/python").inspect()


def test_no_direct_url_is_a_release_from_pypi(tmp_path: Path) -> None:
    installation = _inspect(tmp_path, installer="pip\n")
    assert installation == Installation(
        InstallSource.INDEX, InstallManager.PIP, None, "/env/bin/python"
    )


def test_a_git_url_is_a_git_install(tmp_path: Path) -> None:
    record = {"url": _REPO, "vcs_info": {"vcs": "git", "requested_revision": "v0.12.1"}}
    installation = _inspect(tmp_path, direct_url=record, installer="uv")
    assert installation.source is InstallSource.GIT
    assert installation.location == _REPO


@pytest.mark.parametrize(
    "record",
    [
        {"url": "file:///home/u/My%20Code/gmlw", "dir_info": {"editable": True}},
        {"url": "file:///home/u/My%20Code/gmlw", "dir_info": {}},
    ],
)
def test_a_local_directory_is_a_source_install(tmp_path: Path, record: object) -> None:
    installation = _inspect(tmp_path, direct_url=record)
    assert installation.source is InstallSource.SOURCE
    assert installation.location == "/home/u/My Code/gmlw"


def test_an_archive_url_is_a_source_install(tmp_path: Path) -> None:
    record: dict[str, object] = {"url": "https://example.org/gmlw.whl", "archive_info": {}}
    installation = _inspect(tmp_path, direct_url=record)
    assert installation.source is InstallSource.SOURCE
    assert installation.location == "https://example.org/gmlw.whl"


@pytest.mark.parametrize("text", ["{not json", "[]"])
def test_an_unreadable_direct_url_falls_back_to_pypi(tmp_path: Path, text: str) -> None:
    assert _inspect(tmp_path, direct_url=text).source is InstallSource.INDEX


@pytest.mark.parametrize(
    ("marker", "installer", "manager"),
    [
        ("uv-receipt.toml", "uv", InstallManager.UV_TOOL),
        ("pipx_metadata.json", "pip", InstallManager.PIPX),
        (None, "uv", InstallManager.UV_PIP),
        (None, "pip", InstallManager.PIP),
        (None, None, InstallManager.PIP),
    ],
)
def test_the_manager_is_told_by_the_files_it_leaves(
    tmp_path: Path, marker: str | None, installer: str | None, manager: InstallManager
) -> None:
    assert _inspect(tmp_path, installer=installer, marker=marker).manager is manager


def test_no_installed_distribution_is_an_unbuilt_source(tmp_path: Path) -> None:
    installation = PythonInstallationInspector(lambda: None, tmp_path, "/py").inspect()
    assert installation == Installation(InstallSource.SOURCE, InstallManager.PIP, None, "/py")


def test_the_running_environment_is_read_by_default() -> None:
    # The suite runs from this repository's own environment: some install of gmlw.
    installation = PythonInstallationInspector().inspect()
    assert isinstance(installation.source, InstallSource)
