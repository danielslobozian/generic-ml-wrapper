# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The process-wide handle on the language the wrapper speaks.

Presentation code — the CLI renderers, the TUI, adapters that log — reaches the running
language through the active localiser installed here: :func:`set_active` is called once at
startup with the configured language, and :func:`active` / :func:`t` read it from anywhere
without threading a localiser through every constructor. It is seeded to English at import
so a lookup before startup still resolves.

This is a composition-root concern, and it lives here rather than in a shared folder so
that the fact is visible: **nothing in the application ring may use it.** A use case or a
domain service that needs prose is handed a
:class:`~generic_ml_wrapper.application.port.outbound.localizer.LocalizerPort`; only code
outside the ring may ask the process what language it is speaking.
"""

from __future__ import annotations

from generic_ml_wrapper.adapter.outbound.i18n.json_catalog_localizer import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    JsonCatalogLocalizerFactory,
)
from generic_ml_wrapper.application.port.outbound.localizer import LocalizerPort

__all__ = ["DEFAULT_LANGUAGE", "SUPPORTED_LANGUAGES", "LocalizerPort", "active", "set_active", "t"]

_factory = JsonCatalogLocalizerFactory()

# The process-global active localiser: the language the whole app speaks. Seeded to English
# so every ``active()``/``t()`` lookup resolves even before startup calls ``set_active``.
_active: LocalizerPort = _factory.load(DEFAULT_LANGUAGE)


def resolve_language(env_lang: str | None, default: str = DEFAULT_LANGUAGE) -> str:
    """Map a POSIX ``$LANG`` (e.g. ``fr_FR.UTF-8``) to a supported code, else default."""
    return _factory.resolve_language(env_lang, default)


def load_localizer(lang: str) -> LocalizerPort:
    """Build a localiser for ``lang``, merged over the English base."""
    return _factory.load(lang)


def set_active(localizer: LocalizerPort) -> None:
    """Set the process-global active localiser (called once at startup).

    Args:
        localizer: The localiser for the language the wrapper speaks to the user.
    """
    global _active  # noqa: PLW0603  (one deliberate process-global: the active language)
    _active = localizer


def active() -> LocalizerPort:
    """Return the process-global active localiser (English until ``set_active`` runs)."""
    return _active


def t(key: str, /, **params: object) -> str:
    """Shorthand for ``active().t(key, **params)`` — the app-wide localise call.

    ``key`` is positional-only so a template may use a ``{key}`` field (see
    :meth:`LocalizerPort.t`).

    Args:
        key: The dotted catalogue key.
        params: Values interpolated into the template.

    Returns:
        The formatted string in the active language, English-fallback then raw-key safe.
    """
    return _active.t(key, **params)
