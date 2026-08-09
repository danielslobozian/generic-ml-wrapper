# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass

from generic_ml_wrapper.adapter.inbound.tui.view.switch_choice import SwitchChoice


@dataclass(frozen=True)
class CreateOutcome:
    choice: SwitchChoice | None
    message: str
