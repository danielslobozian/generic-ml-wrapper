# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``RoleRepositoryPort`` backed by the folders under ``~/.gmlw/profile/roles``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.about import read_about, write_about
from generic_ml_wrapper.application.domain.model.role import Role
from generic_ml_wrapper.application.port.outbound.role_repository import RoleRepositoryPort

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_rule_store import (
        FilesystemRuleStore,
    )

_ROOT = "profile/roles"
_RULES = "rules"


class FilesystemRoleRepositoryAdapter(RoleRepositoryPort):
    """Store one role per folder: the code is the folder name, the rest is inside it.

    A ``clock`` is injected so the ``created`` stamp in a new role's sidecar is
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
            home: The ``~/.gmlw`` root holding ``profile/roles/``.
            rules: Reads the rules held inside each role folder.
            clock: Returns "now" for a new role's ``created`` stamp; defaults to the local
                wall clock.
        """
        self._home = home
        self._rules = rules
        self._clock = clock or (lambda: datetime.now(UTC).astimezone())

    def find_all(self) -> tuple[Role, ...]:
        """Return every stored role, sorted by code.

        Returns:
            One role per folder, each carrying the rules it holds.
        """
        root = self._home / _ROOT
        if not root.is_dir():
            return ()
        return tuple(
            self._role(folder) for folder in sorted(p for p in root.iterdir() if p.is_dir())
        )

    def exists(self, role: Role) -> bool:
        """Whether a folder for this role's code is already present."""
        return (self._home / _ROOT / role.code).is_dir()

    def save(self, role: Role) -> None:
        """Create the role's folder, its empty ``rules/`` drop-zone and its sidecar."""
        folder = self._home / _ROOT / role.code
        (folder / _RULES).mkdir(parents=True, exist_ok=True)
        write_about(folder, role.label, role.description, self._clock().isoformat())

    def _role(self, folder: Path) -> Role:
        """Build one role from its folder: the name is the code, the rest is read inside."""
        label, description = read_about(folder)
        return Role(folder.name, label, description, self._rules.find_all(folder / _RULES))
