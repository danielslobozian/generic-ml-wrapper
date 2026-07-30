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
from generic_ml_wrapper.common import paths, settings_registry

if TYPE_CHECKING:
    from pathlib import Path

# Every scalar default is sourced from the registry (the single typed source of truth),
# so a default is declared once — on its Field — not duplicated here. This module keeps
# the *tolerant* reading (a malformed or ill-typed file falls back, never raises); the
# registry supplies the fallback value.
_DEFAULT_CLIENT = cast("str", settings_registry.default_for("client.default"))
_DEFAULT_ROLE = cast("str", settings_registry.default_for("profile.default_role"))
_DEFAULT_ENVIRONMENT = cast("str", settings_registry.default_for("profile.default_environment"))
_DEFAULT_LOG_LEVEL = cast("str", settings_registry.default_for("logging.level"))
_DEFAULT_LOG_TO_FILE = cast("bool", settings_registry.default_for("logging.to_file"))
_DEFAULT_LOG_MAX_BYTES = cast("int", settings_registry.default_for("logging.max_bytes"))
_DEFAULT_LOG_BACKUP_COUNT = cast("int", settings_registry.default_for("logging.backup_count"))
_DEFAULT_COMPRESS_ADAPTER = cast("str", settings_registry.default_for("compress.adapter"))
_DEFAULT_COMPRESS_MODEL = cast("str", settings_registry.default_for("compress.model"))
_DEFAULT_COMPRESS_EFFORT = cast("str", settings_registry.default_for("compress.effort"))

# The valid ``[[hooks]]`` phases, as literal strings (config keeps its own vocabulary of
# string keys rather than importing domain enums, mirroring ``_STARTUP_ACTIVATION``). Kept
# in step with ``domain.service.hook.HookPhase``; a test guards that they agree.
_HOOK_PHASES = frozenset({"pre-launch", "post-session"})


def config_path() -> Path:
    """Return the config file path (``~/.gmlw/config.toml``)."""
    return paths.HOME / "config.toml"


_config_path = config_path  # internal alias, kept for the accessors below


def current_values(path: Path | None = None) -> dict[str, object]:
    """Return the current effective value of every registered scalar setting.

    Reads each setting through its own tolerant accessor, so the map reflects exactly what
    the app will use (defaults where unset). The keys mirror
    :func:`settings_registry.keys`; a test guards that they stay in step.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        A ``dotted.key -> value`` map for the settable scalar keys.
    """
    companion_settings = companion(path)
    transcript_settings = transcript(path)
    compress_settings = compress(path)
    return {
        "client.default": default_client(path),
        "client.args": client_args(path),
        "language.code": language(path),
        "profile.default_role": default_role(path),
        "profile.default_environment": default_environment(path),
        "logging.level": log_level(path),
        "logging.to_file": log_to_file(path),
        "logging.max_bytes": log_max_bytes(path),
        "logging.backup_count": log_backup_count(path),
        "companion.persona": companion_settings.persona,
        "companion.name": companion_settings.name,
        "transcript.enabled": transcript_settings.enabled,
        "transcript.root": transcript_settings.root,
        "compress.adapter": compress_settings.adapter,
        "compress.model": compress_settings.model,
        "compress.effort": compress_settings.effort,
        "hints.show": hints_show(path),
        "update.check": update_check(path),
        "ambient.capability_card": ambient_capability_card(path),
    }


def hints_show(path: Path | None = None) -> bool:
    """Return whether to show a usage-driven tip on the exit receipt (``[hints] show``).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[hints] show`` value, or ``True`` when unset.
    """
    value = _table(_load(path), "hints").get("show")
    return value if isinstance(value, bool) else True


def update_check(path: Path | None = None) -> bool:
    """Return whether to check PyPI for a newer release (``[update] check``).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[update] check`` value, or ``True`` when unset.
    """
    value = _table(_load(path), "update").get("check")
    return value if isinstance(value, bool) else True


def ambient_capability_card(path: Path | None = None) -> bool:
    """Return whether to inject the ambient capability card (``[ambient] capability_card``).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[ambient] capability_card`` value, or ``False`` when unset.
    """
    value = _table(_load(path), "ambient").get("capability_card")
    return value if isinstance(value, bool) else False


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


def client_args(path: Path | None = None) -> dict[str, str]:
    """Return the per-client launch arguments table, or ``{}`` when unset.

    Reads ``[client] args`` — written either as an inline table or as a ``[client.args]``
    sub-table, which TOML treats as the same structure. Tolerant like every reader here:
    a non-table value, or an entry whose name or value is not a string, is skipped rather
    than raised on.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        A ``client -> raw argument string`` map.
    """
    table = _table(_table(_load(path), "client"), "args")
    return {name: value for name, value in table.items() if isinstance(value, str)}


def client_args_for(client: str, path: Path | None = None) -> str:
    """Return the raw argument string configured for one client, or ``""``.

    Args:
        client: The client the run will launch.
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The configured argument string, or ``""`` when the client has none.
    """
    return client_args(path).get(client, "")


def init_version(path: Path | None = None) -> str | None:
    """Return the gmlw version that ran ``init``, or ``None`` when it never has.

    This is the first-class init gate signal: ``None`` means the install is fresh (no
    config) or legacy (a pre-init ``config.toml``), so bare ``gmlw`` must funnel it
    through init before anything else runs.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[init] version`` string, or ``None`` when the marker is absent.
    """
    value = _table(_load(path), "init").get("version")
    return value if isinstance(value, str) and value else None


def language(path: Path | None = None) -> str | None:
    """Return the language gmlw speaks to the user (``[language] code``), or ``None``.

    ``None`` leaves the caller to fall back (to ``$LANG``, then English). This fixes
    gmlw's *own* voice only; it does not force the companion's language.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The configured language code, or ``None`` when unset.
    """
    value = _table(_load(path), "language").get("code")
    return value if isinstance(value, str) and value else None


def default_role(path: Path | None = None) -> str:
    """Return the default role — the functional hat worn — from ``[profile] default_role``.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[profile] default_role`` value, or ``"default"`` when unset.
    """
    value = _table(_load(path), "profile").get("default_role")
    return value if isinstance(value, str) and value else _DEFAULT_ROLE


def default_environment(path: Path | None = None) -> str:
    """Return the default environment — the place work happens — from ``[profile]``.

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[profile] default_environment`` value, or ``"work"`` when unset.
    """
    value = _table(_load(path), "profile").get("default_environment")
    return value if isinstance(value, str) and value else _DEFAULT_ENVIRONMENT


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
    return value if isinstance(value, str) and value else _DEFAULT_LOG_LEVEL


def log_to_file(path: Path | None = None) -> bool:
    """Return whether diagnostics are written to the rolling log file (``[logging] to_file``).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[logging] to_file`` value, or the built-in default.
    """
    value = _table(_load(path), "logging").get("to_file")
    return value if isinstance(value, bool) else _DEFAULT_LOG_TO_FILE


def log_max_bytes(path: Path | None = None) -> int:
    """Return the log file's size cap before it rolls (``[logging] max_bytes``).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[logging] max_bytes`` value, or the built-in default. A non-positive or
        ill-typed value falls back rather than raising — a bad rotation setting must not
        be the thing that stops a run.
    """
    value = _table(_load(path), "logging").get("max_bytes")
    # `bool` is an `int` in Python; exclude it so `max_bytes = true` reads as malformed.
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return _DEFAULT_LOG_MAX_BYTES


def log_backup_count(path: Path | None = None) -> int:
    """Return how many rolled log files to keep (``[logging] backup_count``).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The ``[logging] backup_count`` value, or the built-in default.
    """
    value = _table(_load(path), "logging").get("backup_count")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return _DEFAULT_LOG_BACKUP_COUNT


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
        adapter=adapter if isinstance(adapter, str) and adapter else _DEFAULT_COMPRESS_ADAPTER,
        model=model if isinstance(model, str) and model else _DEFAULT_COMPRESS_MODEL,
        effort=effort if isinstance(effort, str) and effort else _DEFAULT_COMPRESS_EFFORT,
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
        "rules.environment": True,
        "rules.role": True,
    },
    "workflow": {
        "persona": False,
        "me.user": True,
        "me.learned": True,
        "company": True,
        "rules.environment": True,
        "rules.role": True,
    },
    "authoring": {
        "persona": False,
        "me.user": True,
        "me.learned": True,
        "company": True,
        "rules.environment": True,
        "rules.role": True,
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
    legacy_rules = _legacy_rules_table(context)
    resolved: dict[str, SourceSetting] = {}
    for source in context_source.ALL_SOURCES:
        table = _source_table(context, source.key)
        if not table and source in context_source.RULE_AXES:
            table = legacy_rules
        default = defaults[source.key]
        activated = default.activated
        if source.activatable and isinstance(table.get("activated"), bool):
            activated = cast("bool", table["activated"])
        compression = default.compression
        if isinstance(table.get("compression"), bool):
            compression = cast("bool", table["compression"])
        resolved[source.key] = SourceSetting(activated=activated, compression=compression)
    return resolved


def _legacy_rules_table(context: dict[str, object]) -> dict[str, object]:
    """Return a pre-split scalar ``rules`` table, or ``{}`` when there is none.

    Rules used to be one source; they are now two (``rules.environment``/``rules.role``).
    A config written before the split holds ``activated``/``compression`` directly under
    ``rules`` rather than nested axis tables, which tells the two shapes apart without a
    version marker. The old value is honoured for both axes so a user who deliberately
    switched rules off never has that silently undone by the rename.

    Args:
        context: The ``[startup.<mode>.context]`` table.

    Returns:
        The legacy table, or ``{}`` when absent or already in the new nested shape.
    """
    table = context.get("rules")
    if not isinstance(table, dict):
        return {}
    legacy = cast("dict[str, object]", table)
    if any(isinstance(legacy.get(axis), dict) for axis in ("environment", "role")):
        return {}
    return legacy


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
