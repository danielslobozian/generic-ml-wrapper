# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``AxisChooserPort`` at a terminal: a menu of examples plus a "type your own" path.

The forced init's role and environment steps. Rather than a bare free-text box — which
produced folders full of spaces, capitals, and accents — this shows a short concept blurb,
offers a few canonical examples, and adds a "type your own" option. A typed answer keeps
the human wording as the label/description but is reduced to a clean kebab-case slug for
the folder and config value, and the slug is echoed back so the mapping is never a surprise.
A non-TTY run declines to the supplied default, so automation never blocks.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number, emit
from generic_ml_wrapper.application.domain.model.axis import AxisSelection
from generic_ml_wrapper.application.port.outbound.axis_chooser import AxisChooserPort
from generic_ml_wrapper.common.slug import slugify

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis import AxisPrompt
    from generic_ml_wrapper.common.i18n import Localizer

# Sentinel option value: "type a role/environment other than the offered examples".
_TYPE_YOUR_OWN = "\x00type-your-own"


class TtyAxisChooser(AxisChooserPort):
    """Guide the role/environment choice at an interactive terminal."""

    def __init__(self, i18n: Localizer) -> None:
        """Bind the chooser to a localiser for its prompt text.

        Args:
            i18n: The default localiser for the blurb, menu, and echo.
        """
        self._i18n = i18n

    def choose(
        self, prompt: AxisPrompt, default: str, i18n: Localizer | None = None
    ) -> AxisSelection:
        """Offer the examples plus "type your own"; return the resolved selection.

        Args:
            prompt: The per-axis wiring (examples + i18n keys).
            default: The slug used off a terminal or when a typed answer has no slug.
            i18n: The localiser to use; ``None`` falls back to the construction-time one.

        Returns:
            The chosen :class:`AxisSelection`.
        """
        loc = i18n or self._i18n
        emit(loc.t(prompt.intro_key))
        choices = [
            Choice(value=ex.slug, label=loc.t(ex.label_key), description=loc.t(ex.description_key))
            for ex in prompt.examples
        ]
        choices.append(Choice(value=_TYPE_YOUR_OWN, label=loc.t(prompt.type_your_own_key)))
        picked = choose_number(loc.t(prompt.header_key), choices, loc, default=0)
        if picked is None:  # non-TTY, EOF — decline to the default
            return AxisSelection(default, default, default)
        if picked != _TYPE_YOUR_OWN:
            example = next(ex for ex in prompt.examples if ex.slug == picked)
            return AxisSelection(
                example.slug, loc.t(example.label_key), loc.t(example.description_key)
            )
        return self._type_your_own(prompt, default, loc)

    def _type_your_own(self, prompt: AxisPrompt, default: str, loc: Localizer) -> AxisSelection:
        """Read a free-text answer, keep it as the label, and derive + echo its slug."""
        typed = self._read(loc.t(prompt.prompt_key))
        if typed is None or not typed.strip():
            return AxisSelection(default, default, default)
        label = typed.strip()
        slug = slugify(label) or default
        emit(loc.t(prompt.saved_key, slug=slug))
        return AxisSelection(slug, label, label)

    @staticmethod
    def _read(prompt_text: str) -> str | None:
        """Write ``prompt_text`` to stderr and read one line from stdin, or ``None`` off a TTY."""
        if not (sys.stdin.isatty() and sys.stderr.isatty()):
            return None
        print(prompt_text, end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline()
        return None if line == "" else line
