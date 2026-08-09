# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    icon: str
    title: str
    subtitle: str
    action: str
    example: str = ""
    payload: str = ""
    note: str = ""
    disabled: bool = False
