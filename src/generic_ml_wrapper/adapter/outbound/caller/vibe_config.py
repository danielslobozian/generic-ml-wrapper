# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Bootstrap an isolated vibe config that routes the active model through a relay.

The metering gateway copies the user's real ``~/.vibe/config.toml`` into a throwaway
``VIBE_HOME`` and repoints one thing: the ``api_base`` of the provider its active
model uses. Everything else — model definitions, prices, ``api_key_env_var``, tool
permissions — is preserved, so the metered run behaves like the real one but its
traffic detours through the local relay. The API key resolves from the OS keyring,
which is independent of ``VIBE_HOME``, so no credential is copied.
"""

from __future__ import annotations

import tomllib
from typing import cast
from urllib.parse import urlsplit


def active_upstream(source_text: str) -> str | None:
    """Return the ``api_base`` the config's active model talks to, or ``None``.

    Resolves ``active_model`` to its ``[[models]]`` entry (matched by ``name`` or
    ``alias``), then that model's ``[[providers]]`` entry, and returns its
    ``api_base`` (e.g. ``https://api.mistral.ai/v1``).

    Args:
        source_text: The contents of a vibe ``config.toml``.

    Returns:
        The active provider's ``api_base``, or ``None`` if it cannot be resolved.
    """
    try:
        data = tomllib.loads(source_text)
    except tomllib.TOMLDecodeError:
        return None
    active = data.get("active_model")
    if not isinstance(active, str):
        return None
    provider_name = _provider_of(data.get("models"), active)
    if provider_name is None:
        return None
    return _api_base_of(data.get("providers"), provider_name)


def redirect(source_text: str, upstream: str, relay_base_url: str) -> str:
    """Repoint ``upstream``'s host at the relay, keeping its path.

    ``https://api.mistral.ai/v1`` becomes ``http://127.0.0.1:PORT/v1`` — vibe then
    posts ``/v1/chat/completions`` to the relay, which forwards to the real host.

    Args:
        source_text: The contents of a vibe ``config.toml``.
        upstream: The ``api_base`` to repoint (from :func:`active_upstream`).
        relay_base_url: The relay's base URL (``http://127.0.0.1:PORT``).

    Returns:
        The config text with ``upstream`` replaced by the relay-pointed base URL, changed
        only inside the active provider's ``[[providers]]`` table -- so the same URL in a
        comment or in another provider is left alone. Unchanged if the active provider
        cannot be resolved.
    """
    new_api_base = relay_base_url + urlsplit(upstream).path
    provider = _active_provider_name(source_text)
    if provider is None:
        return source_text
    return _repoint_provider(source_text, provider, f'"{upstream}"', f'"{new_api_base}"')


def _active_provider_name(source_text: str) -> str | None:
    try:
        data = tomllib.loads(source_text)
    except tomllib.TOMLDecodeError:
        return None
    active = data.get("active_model")
    if not isinstance(active, str):
        return None
    return _provider_of(data.get("models"), active)


def _repoint_provider(source_text: str, provider_name: str, old: str, new: str) -> str:
    lines = source_text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        if lines[index].strip() != "[[providers]]":
            index += 1
            continue
        end = index + 1
        name: str | None = None
        api_line: int | None = None
        while end < len(lines) and not lines[end].lstrip().startswith("["):
            stripped = lines[end].strip()
            if stripped.startswith("name") and "=" in stripped:
                name = stripped.split("=", 1)[1].strip().strip('"')
            elif stripped.startswith("api_base") and old in lines[end]:
                api_line = end
            end += 1
        if name == provider_name and api_line is not None:
            lines[api_line] = lines[api_line].replace(old, new, 1)
            break
        index = end
    return "".join(lines)


def _provider_of(models: object, active: str) -> str | None:
    if not isinstance(models, list):
        return None
    for entry in cast("list[object]", models):
        if not isinstance(entry, dict):
            continue
        model = cast("dict[str, object]", entry)
        if model.get("name") == active or model.get("alias") == active:
            provider = model.get("provider")
            return provider if isinstance(provider, str) else None
    return None


def _api_base_of(providers: object, name: str) -> str | None:
    if not isinstance(providers, list):
        return None
    for entry in cast("list[object]", providers):
        if not isinstance(entry, dict):
            continue
        provider = cast("dict[str, object]", entry)
        if provider.get("name") == name:
            api_base = provider.get("api_base")
            return api_base if isinstance(api_base, str) else None
    return None
