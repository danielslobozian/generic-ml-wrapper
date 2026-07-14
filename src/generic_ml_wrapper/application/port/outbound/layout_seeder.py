# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for seeding the runtime layout on first run."""

from __future__ import annotations

from abc import ABC, abstractmethod


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
