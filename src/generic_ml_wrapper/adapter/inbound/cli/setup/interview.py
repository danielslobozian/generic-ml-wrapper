# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The setup interview: six questions, asked by the terminal.

The order is the terminal's decision. Language comes first because it sets the voice
everything after it is asked in -- and its own menu is the one that cannot be translated,
so each language is offered under its own name. The client question can end the
interview: with nothing installed there is nothing to configure, so nothing is written.

Every option arrives from the application as a code. The words are looked up here, and
the answer goes back as a code or a resolved domain value. The application is asked what
is on offer and told what was chosen; it is never asked for a label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_axis_chooser import TtyAxisChooser
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_client_picker import (
    choose_client,
    report_no_client,
)
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_language_chooser import TtyLanguageChooser
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_persona_chooser import TtyPersonaChooser
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_text_prompt import TtyTextPrompt
from generic_ml_wrapper.application.domain.model.axis_prompt import (
    ENVIRONMENT_PROMPT,
    ROLE_PROMPT,
)
from generic_ml_wrapper.application.domain.model.init_answers import InitAnswers

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.adapter.inbound.cli.setup.message_source import MessageSource
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo
    from generic_ml_wrapper.application.domain.model.persona import Persona
    from generic_ml_wrapper.application.port.inbound.listed_client import ListedClient

DEFAULT_ROLE = "default"
DEFAULT_ENVIRONMENT = "work"


def run_interview(  # noqa: PLR0913  (one per question, plus what the no-client exit needs)
    *,
    languages: list[str],
    default_language: str,
    default_name: str,
    personas: list[Persona],
    clients: list[ListedClient],
    supported: tuple[ClientInfo, ...],
    system: str,
    localizer_for: Callable[[str], MessageSource],
    seed: MessageSource,
) -> InitAnswers | None:
    """Ask the six questions and return the answers, or ``None`` to stop.

    Args:
        languages: The codes this build ships catalogues for.
        default_language: The code used when the user declines.
        default_name: The name used when the user gives none.
        personas: The personas available to choose from.
        clients: Every supported client with its installed-ness and version.
        supported: Every supported client, for the install commands on the exit path.
        system: The OS name, so those commands are the right ones.
        localizer_for: Builds the catalogue for the chosen language.
        seed: The catalogue the language question itself is asked in -- the language is
            not chosen yet, which is why every language is offered under its own name.

    Returns:
        The settled answers, or ``None`` when no client is installed or the client
        question was declined -- in which case nothing should be persisted.
    """
    language = TtyLanguageChooser(seed).choose(languages, default_language)
    loc = localizer_for(language)

    if not any(client.installed for client in clients):
        report_no_client(supported, system, loc)
        return None

    name = TtyTextPrompt(loc).ask(loc.t("init.name.header"), default_name, loc)
    axes = TtyAxisChooser(loc)
    role = axes.choose(ROLE_PROMPT, DEFAULT_ROLE, loc)
    environment = axes.choose(ENVIRONMENT_PROMPT, DEFAULT_ENVIRONMENT, loc)
    persona = TtyPersonaChooser(loc).choose(personas, loc)
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
