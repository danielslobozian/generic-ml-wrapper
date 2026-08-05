# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""How an import resolved."""

from __future__ import annotations

from enum import Enum


class ImportOutcome(Enum):
    """How an import resolved.

    Attributes:
        IMPORTED: The workflow was installed; nothing was displaced.
        REPLACED: A workflow of the same name was displaced into a backup first.
        REFUSED: A workflow of the same name exists and replacing it was declined.
    """

    IMPORTED = "imported"
    REPLACED = "replaced"
    REFUSED = "refused"
