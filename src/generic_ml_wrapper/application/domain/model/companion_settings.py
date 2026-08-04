# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The resolved companion settings: who is speaking, and to whom."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompanionSettings:
    """Resolved ``[companion]`` settings.

    Attributes:
        persona: The selected persona name, or ``None`` — the companion is invisible
            (no injected persona, no host greeting) until one is chosen.
        name: The name the host greeting addresses the user by, or ``None`` to fall
            back (to the OS user today; to the learned name once that lands).
    """

    persona: str | None
    name: str | None
