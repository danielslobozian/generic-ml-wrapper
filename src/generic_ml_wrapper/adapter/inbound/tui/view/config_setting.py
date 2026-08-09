# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConfigSetting:
    key: str
    value: str
    default: str
    type_name: str
    choices: tuple[str, ...] | None
    description: str
