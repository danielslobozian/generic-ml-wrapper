# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The context sources, their compressor kinds, and the startup modes.

A run's operating context is composed from a fixed set of *sources* (the user's
profile, learned notes, company facts, rules, persona, and — for a workflow — its
base and steps). Which sources are active, and whether each is compressed, is
configured per *mode* (a plain start, a workflow, or authoring). Each source that
can be compressed maps to a *compressor kind* — the strategy chosen for that data
shape (there is no one-size-fits-all compressor). This module is the single, pure
declaration of that taxonomy; the config supplies activation and the prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CompileMode(StrEnum):
    """How a run's context is composed: which mode's activation matrix applies.

    A ``str`` enum so a mode doubles as its config key (``[startup.<mode>]``).
    """

    DEFAULT = "default"
    WORKFLOW = "workflow"
    AUTHORING = "authoring"


class CompressorKind(StrEnum):
    """The compression strategy for a source, by the shape of its data.

    The kind selects which prompt compresses the source (see the config's
    ``[compress.prompts]``); a source with no kind is never compressed by default.
    """

    HUMAN_TOUCH = "human-touch"  # personal, preference-shaped: surface what the user likes
    TECHNICAL = "technical"  # workflow base and steps: technical instructions
    RULES = "rules"  # reflexes/rules: a dedicated prompt


@dataclass(frozen=True)
class ContextSource:
    """One composable context source.

    Attributes:
        key: The config key under ``[startup.<mode>.context]`` (dotted for the
            nested ``me`` group, e.g. ``"me.user"``).
        kind: The default compressor kind, or ``None`` when the source is left
            verbatim by default (``company``, ``persona``, base guidance).
        activatable: Whether config may deactivate it. ``base``/``steps`` are
            intrinsic to a workflow (always present); only their compression toggles.
    """

    key: str
    kind: CompressorKind | None
    activatable: bool = True

    @property
    def kind_name(self) -> str | None:
        """The kind's config name, or ``None`` when the source has no default kind."""
        return self.kind.value if self.kind is not None else None


# The five cross-cutting sources, in composed order (identity/tone first, then facts,
# then reflexes). Governed by the per-mode activation matrix.
PERSONA = ContextSource("persona", None)
ME_USER = ContextSource("me.user", CompressorKind.HUMAN_TOUCH)
ME_LEARNED = ContextSource("me.learned", CompressorKind.HUMAN_TOUCH)
COMPANY = ContextSource("company", None)
RULES = ContextSource("rules", CompressorKind.RULES)

# The workflow-only sources, always present in a workflow/authoring run (a workflow
# without its steps is meaningless); only their compression is configurable.
BASE = ContextSource("base", CompressorKind.TECHNICAL, activatable=False)
STEPS = ContextSource("steps", CompressorKind.TECHNICAL, activatable=False)

# The identity/facts family, composed together (ahead of rules) in every mode.
PROFILE_FAMILY: tuple[ContextSource, ...] = (PERSONA, ME_USER, ME_LEARNED, COMPANY)

# The cross-cutting sources every mode considers, in composed order.
CROSS_CUTTING: tuple[ContextSource, ...] = (*PROFILE_FAMILY, RULES)

# Every source, in composed order (used to seed defaults and iterate config).
ALL_SOURCES: tuple[ContextSource, ...] = (*CROSS_CUTTING, BASE, STEPS)


def includes_workflow(mode: CompileMode) -> bool:
    """Whether a mode composes the workflow's base and steps (workflow/authoring)."""
    return mode in (CompileMode.WORKFLOW, CompileMode.AUTHORING)
