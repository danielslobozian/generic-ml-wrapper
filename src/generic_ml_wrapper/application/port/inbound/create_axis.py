# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for creating a new role or environment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis import AxisKind


@dataclass(frozen=True)
class CreateAxisCommand:
    """A request to create a new role or environment.

    Attributes:
        kind: Which axis to create (role or environment).
        label: The human name the user typed; the slug is derived from it.
        description: An optional fuller line saved to the folder's ``.about.toml``.
        make_default: Also point ``profile.default_<kind>`` at the new slug.
    """

    kind: AxisKind
    label: str
    description: str = ""
    make_default: bool = False


@dataclass(frozen=True)
class CreateAxisResult:
    """The outcome of creating an axis.

    Attributes:
        kind: The axis that was created.
        slug: The kebab-case id derived from the label (the folder name + config value).
        label: The human name the folder recorded.
        made_default: Whether ``profile.default_<kind>`` was pointed at the new slug.
    """

    kind: AxisKind
    slug: str
    label: str
    made_default: bool


class AxisLabelError(ValueError):
    """Raised when a label is empty or slugifies to nothing usable."""


class AxisExistsError(ValueError):
    """Raised when a folder for the derived slug already exists."""


class CreateAxis(ABC):
    """Create a new role or environment slug-folder from a typed label."""

    @abstractmethod
    def execute(self, command: CreateAxisCommand) -> CreateAxisResult:
        """Create the axis folder (and optionally make it the default).

        Args:
            command: The request describing the axis, label, description, and default flag.

        Returns:
            The outcome: the axis, the derived slug, the label, and whether it was made default.

        Raises:
            AxisLabelError: If the label is empty or slugifies to nothing.
            AxisExistsError: If a folder for the derived slug already exists.
        """
