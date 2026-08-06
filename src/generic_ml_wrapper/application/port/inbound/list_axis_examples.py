# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for asking which roles or environments are offered as examples."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis_example import AxisExample
    from generic_ml_wrapper.application.domain.model.axis_kind import AxisKind


class ListAxisExamplesUseCase(ABC):
    """Report the offered examples for one axis: the roles, or the environments.

    Examples, not a closed set -- a user may type an axis nobody anticipated, and that
    is the point of them. What this answers is "what would you like to suggest", which
    is the application's to know and the terminal's to present.
    """

    @abstractmethod
    def execute(self, kind: AxisKind) -> list[AxisExample]:
        """Return the examples offered for ``kind``, in display order."""
