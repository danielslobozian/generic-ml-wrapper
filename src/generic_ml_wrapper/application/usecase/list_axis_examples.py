# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListAxisExamplesUseCase use case: the roles or environments offered as examples."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.axis_kind import AxisKind
from generic_ml_wrapper.application.domain.model.axis_prompt import (
    ENVIRONMENT_EXAMPLES,
    ROLE_EXAMPLES,
)
from generic_ml_wrapper.application.port.inbound.list_axis_examples import ListAxisExamplesUseCase

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis_example import AxisExample


class ListAxisExamplesService(ListAxisExamplesUseCase):
    """Report the offered examples for one axis."""

    def execute(self, kind: AxisKind) -> list[AxisExample]:
        """Return the examples offered for ``kind``, in display order."""
        examples = ROLE_EXAMPLES if kind is AxisKind.ROLE else ENVIRONMENT_EXAMPLES
        return list(examples)
