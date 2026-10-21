# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""How the running gmlw was installed, and the command that upgrades it."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum

PACKAGE = "generic-ml-wrapper"


class InstallSource(Enum):
    """Where the installed distribution came from (PEP 610's ``direct_url.json``)."""

    INDEX = "index"  # a release from PyPI
    GIT = "git"  # a git URL, such as the GitHub repository
    SOURCE = "source"  # a local checkout (editable or not) or an archive file


class InstallManager(Enum):
    """What owns the environment gmlw is installed in."""

    UV_TOOL = "uv tool"
    PIPX = "pipx"
    UV_PIP = "uv pip"  # a plain environment uv installed into (``uv pip``, ``uv sync``)
    PIP = "pip"


@dataclass(frozen=True)
class Installation:
    """The running gmlw's install: its source, its manager, and where they point.

    Attributes:
        source: Where the distribution came from.
        manager: What owns the environment it is in.
        location: The git URL for a git install, the directory or file for a source
            install; ``None`` for a release from PyPI.
        python: The interpreter of that environment, for the pip managers.
    """

    source: InstallSource
    manager: InstallManager
    location: str | None = None
    python: str = "python"

    def upgrade_command(self, version: str) -> str | None:
        """The shell command that moves this install to ``version``.

        A release from PyPI upgrades in place; a git install is reinstalled at the
        release's tag (``v<version>``), since its manager cannot upgrade a URL. A source
        install has no command: only its owner knows how that checkout is kept.

        Args:
            version: The release to move to, e.g. ``"0.13.0"``.

        Returns:
            The command, or ``None`` for a source install.
        """
        if self.source is InstallSource.SOURCE:
            return None
        if self.source is InstallSource.GIT:
            url = f"git+{self.location}@v{version}"
            requirement = shlex.quote(f"{PACKAGE} @ {url}")
            commands = {
                InstallManager.UV_TOOL: f"uv tool install --force {requirement}",
                InstallManager.PIPX: f"pipx install --force {shlex.quote(url)}",
                InstallManager.UV_PIP: f"{self._uv_pip()} {requirement}",
                InstallManager.PIP: f"{self._pip()} {requirement}",
            }
        else:
            commands = {
                InstallManager.UV_TOOL: f"uv tool upgrade {PACKAGE}",
                InstallManager.PIPX: f"pipx upgrade {PACKAGE}",
                InstallManager.UV_PIP: f"{self._uv_pip()} {PACKAGE}",
                InstallManager.PIP: f"{self._pip()} {PACKAGE}",
            }
        return commands[self.manager]

    def _uv_pip(self) -> str:
        return f"uv pip install --python {shlex.quote(self.python)} --upgrade"

    def _pip(self) -> str:
        return f"{shlex.quote(self.python)} -m pip install --upgrade"
