# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for localisation: where a catalogue key becomes a sentence.

The port *is* the contract. There is no second interface behind it: an abstraction the
application owns and an adapter implements is what a port already means, so declaring one
in the domain and extending it here would invent a layer the pattern does not have.

Nothing in the domain renders prose. A domain type carries a catalogue key and the params
to fill it; turning that into a sentence in one language happens outside the ring, through
this port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LocalizerPort(ABC):
    """A resolved string catalogue for one language.

    Where the strings come from — packaged JSON, a bundle, a stub in a test — is a wiring
    choice, which is the whole reason this is a port.
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
