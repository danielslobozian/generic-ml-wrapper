# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Workflow value object: a deployed workflow and the human words behind it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Workflow:
    """A runnable workflow: its slug id, and what its author actually called it.

    The folder name is the slug, because it has to be a safe path segment and a thing
    users type at a shell. The words the author used live in the folder's ``.about.toml``
    beside it — the same split roles and environments already use, so "Nightly ETL" and
    ``nightly-etl`` are the same workflow rather than a choice the author has to make.

    A workflow authored before the sidecar existed has neither, so ``label`` falls back
    to the slug and ``description`` is empty. Nothing is migrated: an older workflow
    simply shows its folder name, exactly as it always did.

    Attributes:
        slug: The kebab-case id — the folder name, and what ``gmlw run`` takes.
        label: The human name, or the slug when the workflow predates the sidecar.
        description: A fuller line, or empty when none was given.
    """

    slug: str
    label: str
    description: str
