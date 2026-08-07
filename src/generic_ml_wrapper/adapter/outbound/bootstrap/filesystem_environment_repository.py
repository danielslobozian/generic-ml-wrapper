# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``EnvironmentRepositoryPort`` backed by the folders under ``~/.gmlw/environments``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.about import read_about, write_about
from generic_ml_wrapper.application.domain.model.environment import Environment
from generic_ml_wrapper.application.port.outbound.environment_repository import (
    EnvironmentRepositoryPort,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_rule_store import (
        FilesystemRuleStore,
    )

_ROOT = "environments"
_RULES = "rules"


class FilesystemEnvironmentRepositoryAdapter(EnvironmentRepositoryPort):
    """Store one environment per folder: the code is the folder name, the rest is inside it.

    A ``clock`` is injected so the ``created`` stamp in a new environment's sidecar is
    deterministic under test.
    """

    def __init__(
        self,
        home: Path,
        rules: FilesystemRuleStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Bind the repository to a ``~/.gmlw`` home and the rule store beneath it.

        Args:
            home: The ``~/.gmlw`` root holding ``environments/``.
            rules: Reads the rules held inside each environment folder.
            clock: Returns "now" for a new environment's ``created`` stamp; defaults to the
                local wall clock.
        """
        self._home = home
        self._rules = rules
        self._clock = clock or (lambda: datetime.now(UTC).astimezone())

    def find_all(self) -> tuple[Environment, ...]:
        """Return every stored environment, sorted by code.

        Returns:
            One environment per folder, each carrying the rules it holds.
        """
        root = self._home / _ROOT
        if not root.is_dir():
            return ()
        return tuple(
            self._environment(folder) for folder in sorted(p for p in root.iterdir() if p.is_dir())
        )

    def exists(self, environment: Environment) -> bool:
        """Whether a folder for this environment's code is already present."""
        return (self._home / _ROOT / environment.code).is_dir()

    def save(self, environment: Environment) -> None:
        """Create the environment's folder, its empty ``rules/`` drop-zone and its sidecar."""
        folder = self._home / _ROOT / environment.code
        (folder / _RULES).mkdir(parents=True, exist_ok=True)
        write_about(folder, environment.label, environment.description, self._clock().isoformat())

    def _environment(self, folder: Path) -> Environment:
        """Build one environment from its folder: the name is the code, the rest is inside."""
        label, description = read_about(folder)
        return Environment(folder.name, label, description, self._rules.find_all(folder / _RULES))
