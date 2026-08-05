# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The DomainError: a user-facing exception carrying a catalogue key, never a raw message.

An exception whose text reaches a person must be localisable the same way any other
user-facing string is. A raw f-string message stored on the exception and later
interpolated with ``str(error)`` bakes in English no matter what language the wrapper is
speaking. :class:`DomainError` closes that gap: a subclass raises with a catalogue key and
the params to fill it, and both are readable off the error.

**Rendering is not this type's job.** The error carries the key and the params; whoever
catches it holds a localiser and renders them. A ``localized(loc)`` method here would mean
handing a port to a domain object to get one line back — the domain reaching outward for a
delivery concern — and the caller must already hold the localiser to have called it at all.

``str(error)`` still works, rendering the key for logs and tracebacks.

It lives in the domain because raising it is the domain's own vocabulary for "the user
asked for something the rules do not allow"; only the rendering, which needs a language,
belongs outside.
"""

from __future__ import annotations


class DomainError(Exception):
    """A user-facing error: a catalogue key plus the params to render it.

    Subclasses keep their existing base (``ValueError``, ``KeyError``, ...) alongside
    this one, so every ``except SomeError`` clause written against the old type still
    matches.
    """

    def __init__(self, catalogue_key: str, **params: object) -> None:
        """Bind the catalogue key and its render params.

        Args:
            catalogue_key: The dotted ``resources/i18n/*.json`` key to render this error.
            params: Values interpolated into the key's template.
        """
        self.catalogue_key = catalogue_key
        self.params = params
        super().__init__(catalogue_key)
