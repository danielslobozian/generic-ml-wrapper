# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The request to point the default environment at a code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetDefaultEnvironmentCommand:
    """The request to point the default environment at a code.

    Attributes:
        code: The environment code to write to ``[profile] default_environment``.
    """

    code: str
