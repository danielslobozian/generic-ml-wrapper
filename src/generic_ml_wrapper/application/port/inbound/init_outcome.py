# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What the init interview resolved, for the caller to narrate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment
    from generic_ml_wrapper.application.domain.model.role import Role


@dataclass(frozen=True)
class InitOutcome:
    """What the init interview resolved, for the caller to narrate.

    Attributes:
        language: The language gmlw will speak to the user.
        name: The name the companion will address the user by.
        role: The default role chosen (code + label + description).
        environment: The default environment chosen (code + label + description).
        persona: The persona chosen, or ``None`` when the companion was left off.
        client: The default client chosen, or ``None`` when none was installed/picked.
        found: The installed clients detected, in canonical order (empty when none).
        fresh: ``True`` when this was a brand-new install (full config seeded);
            ``False`` on a legacy install (the answers were merged into the existing
            config).
        overwrites: On a legacy merge, the ``table.key: old → new`` lines for any
            existing setting a freshly chosen value replaced (empty otherwise).
    """

    language: str
    name: str
    role: Role
    environment: Environment
    persona: str | None
    client: str | None
    found: list[str]
    fresh: bool
    overwrites: tuple[str, ...] = ()
