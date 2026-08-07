# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outcome of adding an environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment


@dataclass(frozen=True)
class AddEnvironmentResult:
    """The outcome of adding an environment.

    Attributes:
        environment: The environment that was stored, carrying the code derived from the
            label.
    """

    environment: Environment
