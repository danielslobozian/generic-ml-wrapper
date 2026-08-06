# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What the setup interview came back with: one answer per question, as codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis_selection import AxisSelection


@dataclass(frozen=True)
class InitAnswers:
    """The settled answers, ready to persist.

    Codes, not labels. Whatever conversation produced them -- a terminal, a script, a
    test -- is the caller's business, and none of it reaches this far.

    Attributes:
        language: The language code gmlw will speak.
        name: The name the companion addresses the user by.
        role: The resolved role -- slug, label and description.
        environment: The resolved environment -- slug, label and description.
        persona: The chosen persona, or ``None`` to leave the companion off.
        client: The chosen default client.
    """

    language: str
    name: str
    role: AxisSelection
    environment: AxisSelection
    persona: str | None
    client: str

    def __post_init__(self) -> None:
        """Reject answers that cannot become a usable install."""
        for field_name in ("language", "name", "client"):
            if not getattr(self, field_name):
                message = f"{field_name} must not be empty"
                raise ValueError(message)
