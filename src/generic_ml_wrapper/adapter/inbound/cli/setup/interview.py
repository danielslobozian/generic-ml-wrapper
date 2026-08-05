# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The setup interview: six questions, asked by the terminal.

The order is the terminal's decision, not the application's. Language comes first
because it sets the voice everything after it is asked in — and its own menu is the one
that cannot be translated, so each language is offered under its own name. The client
comes last, and is the only one that can end the interview: without a client there is
nothing to configure, so nothing is written.

Every option arrives as a code. The words are looked up here, and an answer goes back as
a code. The application is asked what is on offer and told what was chosen; it is never
asked for a label and never given a sentence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_axis_chooser import TtyAxisChooserAdapter
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_client_picker import (
    choose_client,
    report_no_client,
)
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_language_chooser import (
    TtyLanguageChooserAdapter,
)
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_persona_chooser import (
    TtyPersonaChooserAdapter,
)
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_text_prompt import TtyTextPromptAdapter
from generic_ml_wrapper.application.domain.model.axis_kind import AxisKind
from generic_ml_wrapper.application.domain.model.init_answers import InitAnswers

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.cli.setup.message_source import MessageSource
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo
    from generic_ml_wrapper.application.port.inbound.listed_client import ListedClient
    from generic_ml_wrapper.application.domain.model.persona import Persona


def run_interview(  # noqa: PLR0913  (one parameter per question's answer source)
    *,
    languages: list[str],
    default_language: str,
    default_name: str,
    role_examples: object,
    environment_examples: object,
    personas: list[Persona],
    clients: list[ListedClient],
    supported: tuple[ClientInfo, ...],
    system: str,
    localizer_for: object,
) -> InitAnswers | None:
    """Ask the six questions and return the answers, or ``None`` to stop.

    Returns:
        The settled answers, or ``None`` when no client is installed — in which case the
        install commands have been printed and nothing should be persisted.
    """
    language = TtyLanguageChooserAdapter().choose(languages, default_language)
    loc: MessageSource = localizer_for(language)  # type: ignore[operator]

    if not any(client.installed for client in clients):
        report_no_client(supported, system, loc)
        return None

    name = TtyTextPromptAdapter().ask(loc.t("init.name.header"), default_name, loc)
    axes = TtyAxisChooserAdapter()
    role = axes.choose(AxisKind.ROLE, role_examples, loc)
    environment = axes.choose(AxisKind.ENVIRONMENT, environment_examples, loc)
    persona = TtyPersonaChooserAdapter().choose(personas, loc)
    client = choose_client(clients, loc)
    if client is None:  # declined at the last step: nothing to configure
        return None
    return InitAnswers(
        language=language,
        name=name,
        role=role,
        environment=environment,
        persona=persona,
        client=client,
    )
