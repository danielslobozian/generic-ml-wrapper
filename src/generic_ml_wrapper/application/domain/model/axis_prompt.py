# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The per-axis chooser wiring, and the two prompts the guided setup offers."""

from __future__ import annotations

from dataclasses import dataclass

from generic_ml_wrapper.application.domain.model.axis_example import AxisExample


@dataclass(frozen=True)
class AxisPrompt:
    """The fixed, per-axis wiring the chooser needs (role vs environment).

    Attributes:
        examples: The offered menu examples, in display order.
        intro_key: The catalogue key for the concept blurb shown above the menu.
        header_key: The catalogue key for the menu's question line.
        type_your_own_key: The catalogue key for the trailing "type your own" option.
        prompt_key: The catalogue key for the free-text sub-prompt after "type your own".
        saved_key: The catalogue key for the "saved as `<slug>`" echo.
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
