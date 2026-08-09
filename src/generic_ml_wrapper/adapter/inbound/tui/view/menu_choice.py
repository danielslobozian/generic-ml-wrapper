# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuChoice:
    action: str
    job: str | None = None
    session: str | None = None
    workflow: str | None = None
    guided: bool = False
    archive: str | None = None
    client: str | None = None
