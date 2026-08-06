# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Where a catalogue key becomes a sentence, in the language the user chose.

Not a port. Nothing in the application asks for a label: a domain type carries a catalogue
key and the params to fill it, a query returns codes, and a log line is written in English
for whoever debugs it. Turning a key into a sentence needs a language and a reader, and
both of those live at the delivery edge -- which is where this lives, the way Spring's
``MessageSource`` is held by the controller advice rather than by the domain.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MessageSource(ABC):
    """A resolved string catalogue for one language.

    Where the strings come from — packaged JSON, a bundle, a stub in a test — is a wiring
    choice, which is why it is an interface at all.
    """

    @property
    @abstractmethod
    def lang(self) -> str:
        """The language code this localiser renders in."""

    @abstractmethod
    def t(self, key: str, /, **params: object) -> str:
        """Return the template for ``key``, formatted with ``params``.

        A lookup never raises: an unknown key renders as the key itself, so a missing
        translation is visible rather than fatal.

        ``key`` is positional-only so a template may itself use a ``{key}`` field
        without colliding with this parameter.

        Args:
            key: The dotted catalogue key.
            params: Values interpolated into the template's ``{name}`` fields.

        Returns:
            The formatted string.
        """
