# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What ``init`` resolved, for the seeder to persist into a fresh config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment
    from generic_ml_wrapper.application.domain.model.role import Role


@dataclass(frozen=True)
class InitSelections:
    """What ``init`` resolved, for the seeder to persist into a fresh config.

    Attributes:
        version: The gmlw version stamped into the ``[init]`` gate marker.
        language: The language gmlw speaks to the user (``[language] code``).
        name: The name the companion addresses the user by (``[companion] name``).
        role: The default role — its code (``[profile] default_role`` + folder) with its
            label and description (the folder's ``.about.toml``).
        environment: The default environment — its code (``[profile] default_environment``
            + folder) with its label and description.
        persona: The chosen persona, or ``None`` to leave the companion off.
        client: The default client, or ``None`` when none was chosen/installed.
    """

    version: str
    language: str
    name: str
    role: Role
    environment: Environment
    persona: str | None
    client: str | None
