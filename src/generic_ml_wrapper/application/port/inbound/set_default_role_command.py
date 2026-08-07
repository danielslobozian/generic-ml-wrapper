# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The request to point the default role at a code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetDefaultRoleCommand:
    """The request to point the default role at a code.

    Attributes:
        code: The role code to write to ``[profile] default_role``.
    """

    code: str
