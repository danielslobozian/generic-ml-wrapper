# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The request to add an environment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AddEnvironmentCommand:
    """The request to add an environment.

    Attributes:
        label: The human name the user typed; the code is derived from it.
        description: An optional fuller line saved to the folder's ``.about.toml``.
    """

    label: str
    description: str = ""
