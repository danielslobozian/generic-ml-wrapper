# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What an archive turns out to be, asked before anything is moved on its behalf."""

from __future__ import annotations

from enum import Enum


class ArchiveStatus(Enum):
    """Whether an archive can be imported, and if not, why not.

    Three states rather than a boolean because the two failures are not the same
    conversation: a path that is not there is a typo, and a zip that carries no workflow
    is the wrong file. They have always had separate messages; this keeps them separate
    without the use case having to touch the disk to tell them apart.

    Attributes:
        MISSING: Nothing readable at that path.
        INCOMPLETE: Readable, but it does not carry a workflow.
        COMPLETE: A workflow that can be installed.
    """

    MISSING = "missing"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
