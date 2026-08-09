# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientRow:
    client: str
    version: str
    resumable: str
    default: str
    name: str = ""
    note: str = ""
