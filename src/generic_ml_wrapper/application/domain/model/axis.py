# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The role and environment axes: a chosen value, the offered examples, and per-axis prompts.

Role ("the functional hat") and environment ("the place work happens") are the two setup
answers that become folders. Each is chosen from a short menu of examples or typed freely;
the resulting :class:`AxisSelection` carries the technical ``slug`` (folder + config value)
alongside the human ``label`` and ``description`` (persisted to the folder's ``.about.toml``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxisSelection:
    """A resolved role or environment.

    Attributes:
        slug: The kebab-case id — the folder name and the ``[profile]`` config value.
        label: The human name shown in menus and saved to the folder's ``.about.toml``.
        description: A fuller line (the example's blurb, or the text the user typed).
    """

    slug: str
    label: str
    description: str


@dataclass(frozen=True)
class AxisExample:
    """One offered menu example for an axis.

    Attributes:
        slug: The canonical (English) slug the example resolves to, language-independent.
        label_key: The i18n key for the menu label.
        description_key: The i18n key for the menu description.
    """

    slug: str
    label_key: str
    description_key: str


@dataclass(frozen=True)
class AxisPrompt:
    """The fixed, per-axis wiring the chooser needs (role vs environment).

    Attributes:
        examples: The offered menu examples, in display order.
        intro_key: The i18n key for the concept blurb shown above the menu.
        header_key: The i18n key for the menu's question line.
        type_your_own_key: The i18n key for the trailing "type your own" menu option.
        prompt_key: The i18n key for the free-text sub-prompt after "type your own".
        saved_key: The i18n key for the "saved as `<slug>`" echo.
    """

    examples: tuple[AxisExample, ...]
    intro_key: str
    header_key: str
    type_your_own_key: str
    prompt_key: str
    saved_key: str


ROLE_EXAMPLES: tuple[AxisExample, ...] = (
    AxisExample("software-engineer", "init.role.eg.engineer.label", "init.role.eg.engineer.desc"),
    AxisExample("product-owner", "init.role.eg.po.label", "init.role.eg.po.desc"),
    AxisExample("qa-engineer", "init.role.eg.qa.label", "init.role.eg.qa.desc"),
    AxisExample("tech-writer", "init.role.eg.writer.label", "init.role.eg.writer.desc"),
)

ENVIRONMENT_EXAMPLES: tuple[AxisExample, ...] = (
    AxisExample("work", "init.env.eg.work.label", "init.env.eg.work.desc"),
    AxisExample("home", "init.env.eg.home.label", "init.env.eg.home.desc"),
    AxisExample("open-source", "init.env.eg.oss.label", "init.env.eg.oss.desc"),
    AxisExample("personal-project", "init.env.eg.personal.label", "init.env.eg.personal.desc"),
)

ROLE_PROMPT = AxisPrompt(
    examples=ROLE_EXAMPLES,
    intro_key="init.role.intro",
    header_key="init.role.header",
    type_your_own_key="init.axis.type_your_own",
    prompt_key="init.role.prompt",
    saved_key="init.axis.saved_role",
)

ENVIRONMENT_PROMPT = AxisPrompt(
    examples=ENVIRONMENT_EXAMPLES,
    intro_key="init.environment.intro",
    header_key="init.environment.header",
    type_your_own_key="init.axis.type_your_own",
    prompt_key="init.environment.prompt",
    saved_key="init.axis.saved_environment",
)
