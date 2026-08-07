# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Role: the craft the user practises, and the rules that travel with it.

A role is a folder under ``profile/roles/<code>/``. Its rules live inside that folder, so
they are part of the role rather than something looked up beside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.slug import Slug
from generic_ml_wrapper.application.domain.model.uncodable_role_label_error import (
    UncodableRoleLabelError,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.rule import Rule


@dataclass(frozen=True, init=False)
class Role:
    """One role: its code, its human label, its fuller line, and the rules it holds.

    Passing ``None`` for the code derives one from the label — the path a newly typed role
    takes, where the user supplies text and never an identifier. A role read back from disk
    passes both, and neither is re-derived: the folder name and the ``.about.toml`` label
    are persisted independently, so re-deriving would silently rename a role whose label
    someone edited by hand.

    Attributes:
        code: The kebab-case id — the folder name and the ``[profile]`` config value.
        label: The human name shown in menus and saved to the folder's ``.about.toml``.
        description: A fuller line (the example's blurb, or the text the user typed).
        rules: The rules held in the role's ``rules/`` folder, drafts included.
    """

    code: str
    label: str
    description: str
    rules: tuple[Rule, ...] = field(default=())

    def __init__(
        self,
        code: str | None,
        label: str,
        description: str = "",
        rules: tuple[Rule, ...] = (),
    ) -> None:
        """Build a role, deriving the code from the label when none is given.

        Args:
            code: The kebab-case id, or ``None`` to derive one from ``label``.
            label: The human name.
            description: A fuller line; empty when the user gave none.
            rules: The rules the role holds.

        Raises:
            UncodableRoleLabelError: If no code was given and the label reduces to nothing.
        """
        resolved = code if code is not None else Slug.of(label).value
        if not resolved:
            raise UncodableRoleLabelError("error.role.label.invalid", label=label)
        object.__setattr__(self, "code", resolved)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "rules", rules)

    @property
    def draft_count(self) -> int:
        """How many of the role's rules the user has switched off."""
        return sum(1 for rule in self.rules if rule.draft)
