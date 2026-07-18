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

from generic_ml_wrapper.application.domain.model import context_source
from generic_ml_wrapper.common import paths

if TYPE_CHECKING:
    from pathlib import Path

_DEFAULT_CLIENT = "claude"

# The valid ``[[hooks]]`` phases, as literal strings (config keeps its own vocabulary of
# string keys rather than importing domain enums, mirroring ``_STARTUP_ACTIVATION``). Kept
# in step with ``domain.service.hook.HookPhase``; a test guards that they agree.
_HOOK_PHASES = frozenset({"pre-launch", "post-session"})


def _config_path() -> Path:
    return paths.HOME / "config.toml"


def config_exists(path: Path | None = None) -> bool:
    """Report whether the config file is present (the first-run signal).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        ``True`` when the file exists, ``False`` on the first run before it is seeded.
    """
    return (path or _config_path()).exists()


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


def hooks(path: Path | None = None) -> list[tuple[str, str, str | None]]:
    """Return the configured lifecycle hooks from ``[[hooks]]``.

    Each entry is a ``phase`` (``pre-launch`` / ``post-session``), a ``spec`` (an
    importable ``"module:Class"`` / ``"/path.py:Class"``, or a plugin id), and an
    optional ``client`` scope, run in declared order. Entries with an unknown phase or
    a missing phase/spec are dropped (a malformed hook must not break a launch); the
    ``client`` is kept only when it is a non-empty string, else ``None`` (every client).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``(phase, spec, client)`` triples in order (empty when none are configured).
    """
    raw = _load(path).get("hooks")
    if not isinstance(raw, list):
        return []
    triples: list[tuple[str, str, str | None]] = []
    for entry in cast("list[object]", raw):
        if not isinstance(entry, dict):
            continue
        table = cast("dict[str, object]", entry)
        phase = table.get("phase")
        spec = table.get("spec")
        if not (isinstance(phase, str) and phase in _HOOK_PHASES):
            continue
        if not (isinstance(spec, str) and spec):
            continue
        client = table.get("client")
        triples.append((phase, spec, client if isinstance(client, str) and client else None))
    return triples


@dataclass(frozen=True)
class CompressSettings:
    """Resolved ``[compress]`` settings for the typed context compressor.

    Attributes:
        adapter: The generic-ml-cache client adapter to compress through.
        model: The model to compress with.
        effort: The reasoning effort.
        prompts: The override map from ``[compress.prompts]`` — each key is either a
            compressor kind (``human-touch``/``technical``/``rules``) or a specific
            source key (``me.user``, ``company``, …); the value is a prompt-file path.
            The prompt is the user's IP; the repo ships none, so a source stays
            verbatim until a prompt resolves for it.
    """

    adapter: str
    model: str
    effort: str
    prompts: dict[str, str]

    def prompt_for(self, source_key: str, kind: str | None) -> str | None:
        """Resolve the compression prompt for a source: key override, then kind.

        Args:
            source_key: The specific source key (e.g. ``"me.user"``).
            kind: The source's default compressor kind, or ``None``.

        Returns:
            The prompt-file path — the key-level override if present, else the
            kind-level one, else ``None`` (leave the source verbatim).
        """
        direct = self.prompts.get(source_key)
        if direct:
            return direct
        return self.prompts.get(kind) if kind else None


def compress(path: Path | None = None) -> CompressSettings:
    """Return the ``[compress]`` settings, defaulting to gpt-5.4-low via cursor.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The resolved settings; ``prompts`` is empty (every source verbatim) unless
        ``[compress.prompts]`` names prompt files.
    """
    table = _table(_load(path), "compress")
    prompts = {
        key: value
        for key, value in _table(table, "prompts").items()
        if isinstance(value, str) and value
    }
    adapter = table.get("adapter")
    model = table.get("model")
    effort = table.get("effort")
    return CompressSettings(
        adapter=adapter if isinstance(adapter, str) and adapter else "cursor",
        model=model if isinstance(model, str) and model else "gpt-5.4",
        effort=effort if isinstance(effort, str) and effort else "low",
        prompts=prompts,
    )


@dataclass(frozen=True)
class CompanionSettings:
    """Resolved ``[companion]`` settings.

    Attributes:
        persona: The selected persona name, or ``None`` — the companion is invisible
            (no injected persona, no host greeting) until one is chosen.
        name: The name the host greeting addresses the user by, or ``None`` to fall
            back (to the OS user today; to the learned name once that lands).
    """

    persona: str | None
    name: str | None


def companion(path: Path | None = None) -> CompanionSettings:
    """Return the ``[companion]`` settings; the companion is off (invisible) by default.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The resolved settings; ``persona`` is ``None`` unless ``[companion] persona`` is set.
    """
    table = _table(_load(path), "companion")
    persona = table.get("persona")
    name = table.get("name")
    return CompanionSettings(
        persona=persona if isinstance(persona, str) and persona else None,
        name=name if isinstance(name, str) and name else None,
    )


@dataclass(frozen=True)
class SourceSetting:
    """Whether a context source is composed into a run, and whether it is compressed.

    Attributes:
        activated: Include the source in the compiled context. Intrinsic workflow
            sources (``base``/``steps``) are always active regardless of config.
        compression: Attempt to compress the source through its kind's prompt. Only
            takes effect when a prompt resolves (see :meth:`CompressSettings.prompt_for`).
    """

    activated: bool
    compression: bool


# Baked-in per-mode activation for the activatable (cross-cutting) sources. Compression
# defaults off everywhere — it costs tokens and is a no-op until a prompt is configured.
_STARTUP_ACTIVATION: dict[str, dict[str, bool]] = {
    "default": {
        "persona": False,
        "me.user": True,
        "me.learned": True,
        "company": True,
        "rules": True,
    },
    "workflow": {
        "persona": False,
        "me.user": True,
        "me.learned": True,
        "company": True,
        "rules": True,
    },
    "authoring": {
        "persona": False,
        "me.user": True,
        "me.learned": True,
        "company": True,
        "rules": True,
    },
}


def default_startup(mode: str) -> dict[str, SourceSetting]:
    """Return a mode's baked-in activation matrix, with no config file read.

    Args:
        mode: The compile mode (``default``/``workflow``/``authoring``).

    Returns:
        A setting per source key. Intrinsic ``base``/``steps`` are always active;
        cross-cutting sources follow the built-in per-mode defaults; nothing is
        compressed by default.
    """
    activation = _STARTUP_ACTIVATION.get(mode, _STARTUP_ACTIVATION["default"])
    settings: dict[str, SourceSetting] = {}
    for source in context_source.ALL_SOURCES:
        activated = activation.get(source.key, False) if source.activatable else True
        settings[source.key] = SourceSetting(activated=activated, compression=False)
    return settings


def startup(mode: str, path: Path | None = None) -> dict[str, SourceSetting]:
    """Return a mode's activation matrix from ``[startup.<mode>.context]`` over defaults.

    Args:
        mode: The compile mode (``default``/``workflow``/``authoring``).
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        A setting per source key: the config value where given, else the baked-in
        default. ``base``/``steps`` stay always-active (only their compression is read).
    """
    defaults = default_startup(mode)
    context = _table(_table(_table(_load(path), "startup"), mode), "context")
    resolved: dict[str, SourceSetting] = {}
    for source in context_source.ALL_SOURCES:
        table = _source_table(context, source.key)
        default = defaults[source.key]
        activated = default.activated
        if source.activatable and isinstance(table.get("activated"), bool):
            activated = cast("bool", table["activated"])
        compression = default.compression
        if isinstance(table.get("compression"), bool):
            compression = cast("bool", table["compression"])
        resolved[source.key] = SourceSetting(activated=activated, compression=compression)
    return resolved


def _source_table(context: dict[str, object], key: str) -> dict[str, object]:
    """Return the inline table for a (possibly dotted) source key, or ``{}``."""
    table = context
    for part in key.split("."):
        value = table.get(part)
        if not isinstance(value, dict):
            return {}
        table = cast("dict[str, object]", value)
    return table


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
