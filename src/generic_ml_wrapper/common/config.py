# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Read the optional ``~/.gmlw/config.toml``.

The file is optional: every accessor falls back to a sane default when it is
absent or malformed, so the wrapper works with no config at all.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.common import paths

if TYPE_CHECKING:
    from pathlib import Path

_DEFAULT_CLIENT = "claude"


def _config_path() -> Path:
    return paths.HOME / "config.toml"


def _load(path: Path | None = None) -> dict[str, object]:
    target = path or _config_path()
    try:
        with target.open("rb") as handle:
            data: dict[str, object] = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return data


def _table(data: dict[str, object], name: str) -> dict[str, object]:
    value = data.get(name)
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def default_client(path: Path | None = None) -> str:
    """Return the configured default client, or ``"claude"`` when unset.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[client] default`` value, or the built-in default.
    """
    value = _table(_load(path), "client").get("default")
    return value if isinstance(value, str) and value else _DEFAULT_CLIENT


def caller_overrides(path: Path | None = None) -> dict[str, str]:
    """Return the per-client caller overrides from ``[callers]``.

    Each entry maps a client name to an importable ``"module:Class"`` or
    ``"path.py:Class"`` spec, loaded at runtime in place of the built-in caller.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The client-to-spec mapping (empty when none are configured).
    """
    callers = _table(_load(path), "callers")
    return {name: spec for name, spec in callers.items() if isinstance(spec, str) and spec}


def log_level(path: Path | None = None) -> str:
    """Return the configured diagnostic log level from ``[logging] level``.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[logging] level`` value, or ``"warning"`` when unset.
    """
    value = _table(_load(path), "logging").get("level")
    return value if isinstance(value, str) and value else "warning"


def interceptors(path: Path | None = None) -> list[tuple[str, str]]:
    """Return the configured context interceptors from ``[[interceptors]]``.

    Each entry is a ``target`` (the section it transforms) and a ``spec`` (an
    importable ``"module:Class"`` or ``"/path.py:Class"``), applied in declared
    order. Malformed entries are dropped.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``(target, spec)`` pairs in order (empty when none are configured).
    """
    raw = _load(path).get("interceptors")
    if not isinstance(raw, list):
        return []
    pairs: list[tuple[str, str]] = []
    for entry in cast("list[object]", raw):
        if not isinstance(entry, dict):
            continue
        target = cast("dict[str, object]", entry).get("target")
        spec = cast("dict[str, object]", entry).get("spec")
        if isinstance(target, str) and target and isinstance(spec, str) and spec:
            pairs.append((target, spec))
    return pairs


@dataclass(frozen=True)
class CompressSettings:
    """Resolved ``[compress]`` settings for the context compressor.

    Attributes:
        prompt: Path to the compression prompt file, or ``None`` — compression is
            off until this is set (the prompt is the user's IP; the repo ships none).
        adapter: The generic-ml-cache client adapter to compress through.
        model: The model to compress with.
        effort: The reasoning effort.
    """

    prompt: str | None
    adapter: str
    model: str
    effort: str


def compress(path: Path | None = None) -> CompressSettings:
    """Return the ``[compress]`` settings, defaulting to gpt-5.4-low via cursor.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The resolved settings; ``prompt`` is ``None`` (compression off) unless set.
    """
    table = _table(_load(path), "compress")
    prompt = table.get("prompt")
    adapter = table.get("adapter")
    model = table.get("model")
    effort = table.get("effort")
    return CompressSettings(
        prompt=prompt if isinstance(prompt, str) and prompt else None,
        adapter=adapter if isinstance(adapter, str) and adapter else "cursor",
        model=model if isinstance(model, str) and model else "gpt-5.4",
        effort=effort if isinstance(effort, str) and effort else "low",
    )


@dataclass(frozen=True)
class TranscriptSettings:
    """Resolved ``[transcript]`` settings.

    Attributes:
        enabled: Whether to persist the per-call in/out/usage trio (default off).
        root: An override root directory, or ``None`` for ``~/.gmlw/transcripts``.
    """

    enabled: bool
    root: str | None


def transcript(path: Path | None = None) -> TranscriptSettings:
    """Return the ``[transcript]`` settings; disabled by default.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The resolved settings; ``enabled`` is ``False`` unless set to ``true``.
    """
    table = _table(_load(path), "transcript")
    enabled = table.get("enabled")
    root = table.get("root")
    return TranscriptSettings(
        enabled=enabled is True,
        root=root if isinstance(root, str) and root else None,
    )
