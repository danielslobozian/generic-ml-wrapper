# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``SlugMigratorPort``: rename raw-named role/environment folders to slugs.

Installs made before slugs existed carry folders named with whatever the user typed —
spaces, capitals, accents. This renames each to a clean slug, drops an ``.about.toml``
that keeps the old name as the human label (with a best-effort creation date), and
repoints ``[profile] default_role`` / ``default_environment`` when they named the old
folder. Idempotent: a folder already named as its slug is left alone.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.about import write_about
from generic_ml_wrapper.adapter.outbound.config.tomlkit_config_writer import TomlkitConfigWriter
from generic_ml_wrapper.application.domain.model.migration import SlugMigrationReport
from generic_ml_wrapper.application.port.outbound.slug_migrator import SlugMigratorPort
from generic_ml_wrapper.common.fs_time import created_ms
from generic_ml_wrapper.common.slug import slugify, unique_slug

if TYPE_CHECKING:
    from pathlib import Path

_ENVIRONMENTS = "environments"
_ROLES = "profile/roles"
_CONFIG = "config.toml"


class FilesystemSlugMigrator(SlugMigratorPort):
    """Rename legacy role/environment folders under one ``~/.gmlw`` home to clean slugs."""

    def __init__(self, home: Path) -> None:
        """Bind the migrator to the runtime home directory.

        Args:
            home: The ``~/.gmlw`` root whose ``environments/`` and ``profile/roles/`` are scanned.
        """
        self._home = home

    def migrate(self) -> SlugMigrationReport:
        """Rename every raw-named role/environment folder to its slug, once.

        Returns:
            The ``(old, new)`` rename pairs (empty when nothing needed migrating).
        """
        defaults = self._config_defaults()
        renamed: list[tuple[str, str]] = []
        config_updates: list[tuple[str, str, str]] = []
        for root, key in (
            (self._home / _ENVIRONMENTS, "default_environment"),
            (self._home / _ROLES, "default_role"),
        ):
            if not root.is_dir():
                continue
            for folder in sorted(p for p in root.iterdir() if p.is_dir()):
                old = folder.name
                slug = slugify(old)
                if not slug or slug == old:
                    continue  # already a clean slug, or nothing slug-worthy to rename
                created = self._created_iso(folder)
                final = unique_slug(
                    slug,
                    lambda cand, r=root, f=folder: (r / cand).exists() and (r / cand) != f,
                )
                folder.rename(root / final)
                write_about(root / final, old, old, created)
                renamed.append((old, final))
                if defaults.get(key) == old:  # the active default named this folder → repoint it
                    config_updates.append(("profile", key, final))
        if config_updates:
            self._apply_config(config_updates)
        return SlugMigrationReport(renamed=renamed)

    def _config_defaults(self) -> dict[str, str]:
        """Read ``[profile]`` string values from the home's config (empty when absent)."""
        config = self._home / _CONFIG
        if not config.exists():
            return {}
        try:
            data = tomllib.loads(config.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return {}
        profile = data.get("profile", {})
        return {k: v for k, v in profile.items() if isinstance(v, str)}

    def _apply_config(self, entries: list[tuple[str, str, str]]) -> None:
        """Repoint the given ``[profile]`` keys in the home's config, preserving the rest."""
        config = self._home / _CONFIG
        if config.exists():
            TomlkitConfigWriter().merge(config, entries)

    @staticmethod
    def _created_iso(folder: Path) -> str:
        """The folder's best-effort creation time as ISO-8601 (falls back to now)."""
        ms = created_ms(folder)
        when = datetime.fromtimestamp(ms / 1000, tz=UTC) if ms else datetime.now(UTC)
        return when.astimezone().isoformat()
