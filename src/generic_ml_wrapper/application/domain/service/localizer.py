# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ``Localizer`` abstraction: a catalogue key rendered in one language.

This is the domain-owned contract every catalogue implementation satisfies. The
outbound :class:`~generic_ml_wrapper.application.port.outbound.localizer.LocalizerPort`
extends it, so the dependency points inward (port -> domain) and the domain never
reaches out to a port — the same shape as :class:`.diagnostics.Diagnostics`.

Nothing in the application ring may reach for a *process-wide* localiser: which language
the wrapper speaks is a wiring decision, and code that reads it from a global cannot be
run twice in one process with two answers. Collaborators that need to render prose are
handed one of these.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Localizer(ABC):
    """A resolved string catalogue for one language."""

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
