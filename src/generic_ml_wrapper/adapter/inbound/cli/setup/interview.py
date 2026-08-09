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

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_client_picker import (
    choose_client,
    report_no_client,
)
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_environment_chooser import (
    TtyEnvironmentChooser,
)
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_language_chooser import TtyLanguageChooser
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_persona_chooser import TtyPersonaChooser
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_role_chooser import TtyRoleChooser
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_text_prompt import TtyTextPrompt
from generic_ml_wrapper.adapter.inbound.common.i18n.language_context_holder import (
    LanguageContextHolder,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import get_active
from generic_ml_wrapper.application.domain.model.init_answers import InitAnswers

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo
    from generic_ml_wrapper.application.domain.model.persona import Persona
    from generic_ml_wrapper.application.port.inbound.list_environment_examples import (
        ListEnvironmentExamplesUseCase,
    )
    from generic_ml_wrapper.application.port.inbound.list_role_examples import (
        ListRoleExamplesUseCase,
    )
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
    role_examples: ListRoleExamplesUseCase,
    environment_examples: ListEnvironmentExamplesUseCase,
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
        role_examples: Supplies the roles offered as starting points.
        environment_examples: Supplies the environments offered as starting points.

    Returns:
        The settled answers, or ``None`` when no client is installed or the client
        question was declined -- in which case nothing should be persisted.
    """
    language = TtyLanguageChooser(get_active()).choose(languages, default_language)
    LanguageContextHolder.set_language(language)
    message_source = get_active()

    if not any(client.installed for client in clients):
        report_no_client(supported, system, message_source)
        return None

    name = TtyTextPrompt(message_source).ask(
        message_source.get_message("init.name.header"), default_name, message_source
    )
    role = TtyRoleChooser(message_source, role_examples).choose(DEFAULT_ROLE, message_source)
    environment = TtyEnvironmentChooser(message_source, environment_examples).choose(
        DEFAULT_ENVIRONMENT, message_source
    )
    persona = TtyPersonaChooser(message_source).choose(personas, message_source)
    client = choose_client(clients, message_source)
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
