# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UsageView:
    job: str
    empty: bool
    summary: str
    model_rows: tuple[tuple[str, ...], ...]
    session_rows: tuple[tuple[str, ...], ...]
