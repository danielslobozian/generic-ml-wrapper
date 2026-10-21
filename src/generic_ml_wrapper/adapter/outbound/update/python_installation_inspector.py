# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``InstallationPort`` read off the running environment's packaging metadata, stdlib-only."""

from __future__ import annotations

import json
import sys
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import unquote, urlsplit

from generic_ml_wrapper.application.domain.model.installation import (
    PACKAGE,
    Installation,
    InstallManager,
    InstallSource,
)
from generic_ml_wrapper.application.port.outbound.installation import InstallationPort

if TYPE_CHECKING:
    from collections.abc import Callable

# The files an environment's manager leaves at its root: uv's for a ``uv tool``
# environment, pipx's for one of its venvs.
_UV_TOOL_RECEIPT = "uv-receipt.toml"
_PIPX_METADATA = "pipx_metadata.json"


def _installed() -> metadata.Distribution | None:
    try:
        return metadata.distribution(PACKAGE)
    except metadata.PackageNotFoundError:
        return None


class PythonInstallationInspector(InstallationPort):
    """Tell the source from PEP 610's ``direct_url.json``, the manager from the files it leaves.

    A release installed from PyPI has no ``direct_url.json``; a git URL, a local
    directory or an archive file each record one. The environment's root says who owns
    it: ``uv tool`` and ``pipx`` leave a file of their own there, and the
    distribution's ``INSTALLER`` tells uv from pip in a plain environment.
    """

    def __init__(
        self,
        distribution: Callable[[], metadata.Distribution | None] = _installed,
        prefix: Path | None = None,
        python: str | None = None,
    ) -> None:
        """Read the given environment; the running one by default.

        Args:
            distribution: Finds gmlw's installed distribution, ``None`` when there is none.
            prefix: The environment's root (``sys.prefix``).
            python: The environment's interpreter (``sys.executable``).
        """
        self._distribution = distribution
        self._prefix = Path(sys.prefix) if prefix is None else prefix
        self._python = sys.executable if python is None else python

    def inspect(self) -> Installation:
        """Return how gmlw was installed; a source install when it is not installed at all.

        Returns:
            The installation.
        """
        found = self._distribution()
        if found is None:
            return Installation(InstallSource.SOURCE, InstallManager.PIP, None, self._python)
        source, location = _source(found)
        return Installation(source, self._manager(found), location, self._python)

    def _manager(self, found: metadata.Distribution) -> InstallManager:
        if (self._prefix / _UV_TOOL_RECEIPT).is_file():
            return InstallManager.UV_TOOL
        if (self._prefix / _PIPX_METADATA).is_file():
            return InstallManager.PIPX
        installer = (found.read_text("INSTALLER") or "").strip()
        return InstallManager.UV_PIP if installer == "uv" else InstallManager.PIP


def _source(found: metadata.Distribution) -> tuple[InstallSource, str | None]:
    """The source and its location, from ``direct_url.json`` (PyPI when there is none)."""
    try:
        decoded: object = json.loads(found.read_text("direct_url.json") or "null")
    except ValueError:
        decoded = None
    if not isinstance(decoded, dict):
        return InstallSource.INDEX, None
    record = cast("dict[str, object]", decoded)
    raw = record.get("url")
    url = raw if isinstance(raw, str) and raw else None
    vcs = record.get("vcs_info")
    if isinstance(vcs, dict) and cast("dict[str, object]", vcs).get("vcs") == "git":
        return InstallSource.GIT, url
    return InstallSource.SOURCE, _local(url)


def _local(url: str | None) -> str | None:
    """A ``file://`` URL as the path it names; any other URL unchanged."""
    if url is None:
        return None
    parts = urlsplit(url)
    return unquote(parts.path) if parts.scheme == "file" else url
