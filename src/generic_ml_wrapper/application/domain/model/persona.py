# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A persona: the wrapper's optional tone, and its free host greeting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    """One selectable persona — its metadata, greeting template, and tone block.

    Attributes:
        name: The persona's identifier (its file stem / config value).
        description: A one-line summary, shown by ``gmlw persona list``.
        greeting: The host-greeting template, with ``{name}``/``{daypart}``/
            ``{repo_note}`` slots the wrapper fills from live facts (free, no tokens).
        body: The tone block injected into the client's context when the persona
            source is active (identity, dimensions, do/don't).
    """

    name: str
    description: str
    greeting: str
    body: str
