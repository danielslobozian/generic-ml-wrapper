# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Which axis a value belongs to: the role or the environment."""

from __future__ import annotations

from enum import Enum


class AxisKind(Enum):
    """Which axis a value belongs to: the role or the environment.

    The ``value`` doubles as the config-key suffix (``profile.default_<value>``) and picks
    the folder root (``profile/roles/`` for the role, ``environments/`` for the environment).
    """

    ROLE = "role"
    ENVIRONMENT = "environment"
