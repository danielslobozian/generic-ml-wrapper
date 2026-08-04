# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The WorkflowBackup value object: a workflow that was moved aside, and where it went."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowBackup:
    """A displaced workflow -- what it was called, and where it is now.

    Handed back when a workflow is moved out of the way, and handed in again to put it
    back. It travels as an object rather than a bare path so a caller never has to
    reconstruct where something went, or hold a path it is expected to reason about:
    restoring is "put this back", not "move that string to this other string".

    ``location`` is a string rather than a filesystem path because the domain does not
    name filesystem types -- where a backup lives is the adapter's business, and the
    domain only carries the answer far enough to hand it back.

    Attributes:
        name: The workflow's slug.
        location: Where the displaced copy now lives.
    """

    name: str
    location: str

    def __post_init__(self) -> None:
        """Reject a backup that could not be restored or reported."""
        if not self.name:
            message = "name must not be empty"
            raise ValueError(message)
        if not self.location:
            message = "location must not be empty"
            raise ValueError(message)
