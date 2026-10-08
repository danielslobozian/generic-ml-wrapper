# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Bootstrap an isolated vibe config that routes the active model through a relay.

The metering gateway copies the user's real ``~/.vibe/config.toml`` into a throwaway
``VIBE_HOME`` and repoints one thing: the ``api_base`` of the provider its active
model uses. Everything else — model definitions, prices, ``api_key_env_var``, tool
permissions — is preserved, so the metered run behaves like the real one but its
traffic detours through the local relay. The API key resolves from the OS keyring,
which is independent of ``VIBE_HOME``, so no credential is copied.

A fresh vibe install writes neither ``active_model`` nor any ``[[models]]`` or
``[[providers]]``: it runs on built-ins it keeps in code. When the config leaves the
active model on those built-ins, the upstream is vibe's default ``mistral`` provider,
and the redirect adds that provider's table, pointed at the relay.
"""

from __future__ import annotations

import tomllib
from typing import cast
from urllib.parse import urlsplit

# vibe's built-in provider, and the model keys (unset, alias, name) that resolve to it.
_DEFAULT_PROVIDER = "mistral"
_DEFAULT_API_BASE = "https://api.mistral.ai/v1"
_DEFAULT_MODEL_KEYS = frozenset({"", "mistral-medium-3.5", "mistral-vibe-cli-latest"})
# A [[providers]] entry replaces the built-in one wholesale (vibe merges them by name),
# so it restates the built-in's key variable and backend; the backend fills in the rest.
_DEFAULT_PROVIDER_TABLE = """
[[providers]]
name = "mistral"
api_base = "{api_base}"
api_key_env_var = "MISTRAL_API_KEY"
backend = "mistral"
"""


def active_upstream(source_text: str) -> str | None:
    """Return the ``api_base`` the config's active model talks to, or ``None``.

    Resolves ``active_model`` to its ``[[models]]`` entry (matched by ``name`` or
    ``alias``), then that model's ``[[providers]]`` entry, and returns its
    ``api_base`` (e.g. ``https://api.mistral.ai/v1``). An unset ``active_model``, or
    one naming vibe's built-in default model, resolves to the built-in provider.

    Args:
        source_text: The contents of a vibe ``config.toml``.

    Returns:
        The active provider's ``api_base``, or ``None`` if it cannot be resolved.
    """
    try:
        data = tomllib.loads(source_text)
    except tomllib.TOMLDecodeError:
        return None
    provider_name = _provider_name(data)
    if provider_name is None:
        return None
    api_base = _api_base_of(data.get("providers"), provider_name)
    if api_base is None and provider_name == _DEFAULT_PROVIDER:
        return _DEFAULT_API_BASE
    return api_base


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
        comment or in another provider is left alone. When that provider is vibe's
        built-in one and the config has no table for it, a table is appended. Unchanged
        if the active provider cannot be resolved.
    """
    new_api_base = relay_base_url + urlsplit(upstream).path
    try:
        data = tomllib.loads(source_text)
    except tomllib.TOMLDecodeError:
        return source_text
    provider = _provider_name(data)
    if provider is None:
        return source_text
    if (
        provider == _DEFAULT_PROVIDER
        and upstream == _DEFAULT_API_BASE
        and _api_base_of(data.get("providers"), provider) is None
    ):
        return _with_default_provider(source_text, new_api_base)
    return _repoint_provider(source_text, provider, f'"{upstream}"', f'"{new_api_base}"')


def _provider_name(data: dict[str, object]) -> str | None:
    active = data.get("active_model", "")
    if not isinstance(active, str):
        return None
    provider = _provider_of(data.get("models"), active)
    if provider is None and active in _DEFAULT_MODEL_KEYS:
        return _DEFAULT_PROVIDER
    return provider


def _with_default_provider(source_text: str, api_base: str) -> str:
    separator = "" if not source_text or source_text.endswith("\n") else "\n"
    return source_text + separator + _DEFAULT_PROVIDER_TABLE.format(api_base=api_base)


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
