# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionChoice:
    session_id: str
    client: str
    cwd: str | None
    resumable: bool
    date: str
    is_latest: bool
    usage: str = ""
