# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for seeding the runtime layout on first run."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InitSelections:
    """What ``init`` resolved, for the seeder to persist into a fresh config.

    Attributes:
        version: The gmlw version stamped into the ``[init]`` gate marker.
        language: The language gmlw speaks to the user (``[language] code``).
        name: The name the companion addresses the user by (``[companion] name``).
        role: The default role — the functional hat (``[profile] default_role``).
        environment: The default environment — the place work happens.
        persona: The chosen persona, or ``None`` to leave the companion off.
        client: The default client, or ``None`` when none was chosen/installed.
    """

    version: str
    language: str
    name: str
    role: str
    environment: str
    persona: str | None
    client: str | None


@dataclass(frozen=True)
class InitPersist:
    """The result of persisting an init pass, for the caller to narrate.

    Attributes:
        fresh: ``True`` when a brand-new config was written, ``False`` when the answers
            were merged into a pre-existing (legacy) config.
        overwrites: Human-readable ``table.key: old → new`` lines for each existing
            setting the merge replaced with a freshly chosen value (empty on a fresh
            install, or when the merge only added new keys). Surfaced so a changed
            setting is never dropped silently.
    """

    fresh: bool
    overwrites: tuple[str, ...] = ()


class LayoutSeederPort(ABC):
    """Create the wrapper's runtime directories and a default config, missing-only."""

    @abstractmethod
    def ensure(self, default_client: str | None = None, persona: str | None = None) -> None:
        """Create any missing runtime directories and seed a default config.

        Idempotent: existing directories and an existing config are left untouched.

        Args:
            default_client: When seeding a new config, bake this in as the active
                ``[client] default``. ``None`` seeds the commented placeholder, so
                the built-in default applies until the file is edited.
            persona: When seeding a new config, bake this in as the active
                ``[companion] persona``. ``None`` seeds the commented placeholder.
        """

    @abstractmethod
    def initialize(self, selections: InitSelections) -> InitPersist:
        """Persist an init pass, creating directories as needed.

        Fresh install (no config): write a full config with every selection baked in,
        including the ``[init]`` gate marker. Legacy install (a config already exists):
        **merge** every captured answer into the existing file — creating any missing
        table and setting each key — while preserving the user's other settings,
        comments, and formatting exactly (a round-trip edit, not a rewrite). The persona
        and client are written only when one was chosen. Nothing the user set is lost.

        Args:
            selections: What the init interview resolved.

        Returns:
            An :class:`InitPersist`: whether the write was fresh, and any existing
            settings the merge replaced.
        """
