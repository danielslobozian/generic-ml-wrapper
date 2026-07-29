# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A persona: the wrapper's optional tone, and its free host greeting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

_NO_DIMENSIONS: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True)
class Persona:
    """One selectable persona — its metadata, greeting template, and tone block.

    Attributes:
        name: The persona's identifier (its file stem / config value).
        description: A one-line summary, shown by ``gmlw persona list``.
        greeting: The host-greeting template, with ``{name}``/``{daypart}``/
            ``{repo_note}`` slots the wrapper fills from live facts (free, no tokens).
        body: The tone block injected into the client's context when the persona
            source is active (identity, do/don't).
        dimensions: The declared tone axes (``Warmth``, ``Verbosity``, ``Formality``,
            ``Proactivity``) mapped to their level. Declared in frontmatter rather than
            the body, so they name the axes for evaluation without spending context on
            every turn. Empty for a persona that declares none.
    """

    name: str
    description: str
    greeting: str
    body: str
    dimensions: Mapping[str, str] = _NO_DIMENSIONS
