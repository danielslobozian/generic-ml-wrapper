# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The environment step of the forced init, at a terminal.

Rather than a bare free-text box — which produced folders full of spaces, capitals and
accents — this shows a short concept blurb, offers the packaged starting points, and adds a
"type your own" option. A typed answer keeps the human wording as the label and description
but is reduced to a clean kebab-case code for the folder and config value, and the code is
echoed back so the mapping is never a surprise. A non-TTY run declines to the supplied
default, so automation never blocks.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_prompt import Choice, choose_number, emit
from generic_ml_wrapper.application.domain.model.environment import Environment
from generic_ml_wrapper.application.domain.model.uncodable_environment_label_error import (
    UncodableEnvironmentLabelError,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.cli.setup.message_source import MessageSource
    from generic_ml_wrapper.application.port.inbound.list_environment_examples import (
        ListEnvironmentExamplesUseCase,
    )

# Sentinel option value: "type an environment other than the offered examples".
_TYPE_YOUR_OWN = "\x00type-your-own"
_INTRO = "init.environment.intro"
_HEADER = "init.environment.header"
_TYPE_YOUR_OWN_KEY = "init.environment.type_your_own"
_PROMPT = "init.environment.prompt"
_SAVED = "init.environment.saved"


class TtyEnvironmentChooser:
    """Guide the environment choice at an interactive terminal."""

    def __init__(self, i18n: MessageSource, examples: ListEnvironmentExamplesUseCase) -> None:
        """Bind the chooser to a localiser and the environments it offers.

        Args:
            i18n: The default localiser for the blurb, menu, and echo.
            examples: Supplies the offered starting-point environments.
        """
        self._i18n = i18n
        self._examples = examples

    def choose(self, default: str, i18n: MessageSource | None = None) -> Environment:
        """Offer the examples plus "type your own"; return the chosen environment.

        Args:
            default: The code used off a terminal, or when a typed answer yields none.
            i18n: The localiser to use; ``None`` falls back to the construction-time one.

        Returns:
            The chosen environment.
        """
        loc = i18n or self._i18n
        offered = self._examples.execute()
        emit(loc.t(_INTRO))
        choices = [
            Choice(value=env.code, label=loc.t(env.label), description=loc.t(env.description))
            for env in offered
        ]
        choices.append(Choice(value=_TYPE_YOUR_OWN, label=loc.t(_TYPE_YOUR_OWN_KEY)))
        picked = choose_number(loc.t(_HEADER), choices, loc, default=0)
        if picked is None:  # non-TTY, EOF — decline to the default
            return Environment(default, default, default)
        if picked != _TYPE_YOUR_OWN:
            chosen = next(env for env in offered if env.code == picked)
            return Environment(chosen.code, loc.t(chosen.label), loc.t(chosen.description))
        return self._type_your_own(default, loc)

    def _type_your_own(self, default: str, loc: MessageSource) -> Environment:
        """Read a free-text answer, keep it as the label, and derive + echo its code."""
        typed = self._read(loc.t(_PROMPT))
        if typed is None or not typed.strip():
            return Environment(default, default, default)
        label = typed.strip()
        try:
            environment = Environment(None, label, label)
        except UncodableEnvironmentLabelError:
            # Nothing codeable in what they typed; keep the default rather than refuse a
            # setup step the user cannot skip.
            return Environment(default, default, default)
        emit(loc.t(_SAVED, code=environment.code))
        return environment

    @staticmethod
    def _read(prompt_text: str) -> str | None:
        """Write ``prompt_text`` to stderr and read one line from stdin, or ``None`` off a TTY."""
        if not (sys.stdin.isatty() and sys.stderr.isatty()):
            return None
        print(prompt_text, end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline()
        return None if line == "" else line
