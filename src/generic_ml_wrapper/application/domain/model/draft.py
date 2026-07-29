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
        name: The workflow name the session settled on, or ``None`` if unnamed. Older
            interviews wrote a kebab-case name here directly; newer ones write a
            ``label`` instead and let gmlw derive the slug from it.
        finished: Whether the session declared the workflow ready to deploy.
        label: The human name the session settled on, or ``None``. When present it is
            what the slug is derived from, and what the deployed folder records.
        description: A fuller line describing the workflow, or empty.
    """

    name: str | None
    finished: bool
    label: str | None = None
    description: str = ""


@dataclass(frozen=True)
class Draft:
    """An authoring draft still on disk, and what its marker says about it.

    A draft outlives the session that made it: an interview the user walked away from
    leaves its folder behind so nothing is lost. Until the marker says otherwise the
    workflow has no name, so the draft is identified by the authoring session that
    created it — ``create_draft`` keys the folder by ``session_id``, which is what makes
    a draft findable again without storing a path anywhere.

    Attributes:
        key: The authoring session id the folder is named after (``create-workflow_007``).
        path: The absolute path to the draft folder.
        name: The workflow name its marker proposes, or ``None`` while unnamed.
        finished: Whether its marker declares the workflow ready to deploy. A finished
            draft that is still here was blocked from deploying — its name was taken, or
            was unusable.
    """

    key: str
    path: str
    name: str | None
    finished: bool
