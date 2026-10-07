# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Localisation: a tiny JSON-backed string catalogue with English fallback.

The catalogue lives in packaged ``resources/i18n/<lang>.json`` as flat, dotted keys
mapped to ``str.format`` templates. A :class:`Localizer` merges the chosen language over
English, so a missing translation degrades to English rather than a raw key. This is
deliberately *not* gettext: app-wide copy, no plural rules (labels dodge plurals with the
``job(s)`` convention), zero dependencies.

Every user-facing string and every diagnostic log line the wrapper emits routes through a
localiser. Deep code (adapters that log, the ``format_*`` renderers) reaches the running
language through the **process-global active localiser** — :func:`set_active` is called once
at startup with the configured language, and :func:`active` / :func:`t` read it from
anywhere without threading a :class:`Localizer` through every constructor. It is seeded to
English at import so a lookup before startup still resolves.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import cast

# The languages the wrapper can speak to the user. English is the base and the fallback.
SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "fr")
_DEFAULT = "en"


class Localizer:
    """A resolved string catalogue for one language, English-merged, with parameters."""

    def __init__(self, lang: str, catalog: dict[str, str]) -> None:
        """Bind a language code to its (already English-merged) catalogue.

        Args:
            lang: The resolved language code (one of ``SUPPORTED_LANGUAGES``).
            catalog: Flat ``dotted.key -> template`` map, English keys already merged in.
        """
        self.lang = lang
        self._catalog = catalog

    def t(self, key: str, /, **params: object) -> str:
        """Return the template for ``key``, formatted with ``params``.

        Falls back to English (already merged in) and finally to ``key`` itself, so a
        lookup never raises and an unknown key is visible rather than fatal.

        ``key`` is positional-only so a template may itself use a ``{key}`` field without
        colliding with this parameter.

        Args:
            key: The dotted catalogue key.
            params: Values interpolated into the template's ``{name}`` fields.

        Returns:
            The formatted string, or the raw template when a param is missing.
        """
        template = self._catalog.get(key, key)
        if not params:
            return template
        try:
            return template.format(**params)
        except (KeyError, IndexError, ValueError):
            return template


def resolve_language(env_lang: str | None, default: str = _DEFAULT) -> str:
    """Map a POSIX ``$LANG`` (e.g. ``fr_FR.UTF-8``) to a supported code, else default.

    Args:
        env_lang: The raw ``$LANG`` value, or ``None`` when unset.
        default: The code to fall back to when unset or unsupported.

    Returns:
        A code in ``SUPPORTED_LANGUAGES``.
    """
    if not env_lang:
        return default
    code = env_lang.split(".")[0].split("_")[0].strip().lower()
    return code if code in SUPPORTED_LANGUAGES else default


def load_localizer(lang: str) -> Localizer:
    """Build a :class:`Localizer` for ``lang``, merged over the English base.

    Args:
        lang: The language code to load; unknown keys fall back to English.

    Returns:
        A ready-to-use localiser.
    """
    base = _read_catalog(_DEFAULT)
    catalog = base if lang == _DEFAULT else {**base, **_read_catalog(lang)}
    return Localizer(lang, catalog)


def _read_catalog(lang: str) -> dict[str, str]:
    """Read ``resources/i18n/<lang>.json`` as a flat ``str -> str`` map (empty if absent)."""
    path = resources.files("generic_ml_wrapper").joinpath("resources", "i18n", f"{lang}.json")
    if not path.is_file():
        return {}
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in cast("dict[object, object]", raw).items()}


# The process-global active localiser: the language the whole app speaks. Seeded to English
# so every ``active()``/``t()`` lookup resolves even before startup calls ``set_active``.
_active: Localizer = load_localizer(_DEFAULT)


def set_active(localizer: Localizer) -> None:
    """Set the process-global active localiser (called once at startup).

    Args:
        localizer: The localiser for the language the wrapper speaks to the user.
    """
    global _active  # noqa: PLW0603  (one deliberate process-global: the active language)
    _active = localizer


def active() -> Localizer:
    """Return the process-global active localiser (English until ``set_active`` runs).

    Returns:
        The current active localiser.
    """
    return _active


def t(key: str, /, **params: object) -> str:
    """Shorthand for ``active().t(key, **params)`` — the app-wide localise call.

    ``key`` is positional-only so a template may use a ``{key}`` field (see
    :meth:`Localizer.t`).

    Args:
        key: The dotted catalogue key.
        params: Values interpolated into the template.

    Returns:
        The formatted string in the active language, English-fallback then raw-key safe.
    """
    return _active.t(key, **params)
