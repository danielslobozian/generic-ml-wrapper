# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The DraftMarker: what an authoring session leaves for gmlw to deploy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DraftMarker:
    """The convergence marker a create-workflow session writes into its draft folder.

    Authoring runs in a scratch draft folder because the workflow's name is decided at
    the end, not the start. At convergence the client writes ``meta.json`` naming the
    workflow and declaring it finished; gmlw reads that marker to decide whether (and
    where) to deploy the draft. A missing or malformed marker parses to
    ``DraftMarker(None, finished=False)`` — an incomplete draft that is left in place,
    never deployed.

    Attributes:
        name: The workflow name the session settled on, or ``None`` if unnamed.
        finished: Whether the session declared the workflow ready to deploy.
    """

    name: str | None
    finished: bool
