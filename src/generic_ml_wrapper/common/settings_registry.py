# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The config registry: one typed source of truth for every settable scalar key.

A :class:`GmlwSettings` pydantic-settings model declares each user-tunable *scalar* key
once — its type, default, allowed values and description. Every surface renders from it:
the ``config`` commands list/validate against it, help describes keys from it, and
:mod:`generic_ml_wrapper.common.config` sources its defaults here instead of duplicating
literals.

Scope: the **settable scalar keys** only (``client.default``, ``profile.*``,
``logging.level``, ``companion.*``, ``transcript.*``, ``compress.{adapter,model,effort}``,
``language.code``). The structural/list settings (``[[hooks]]``, ``[[interceptors]]``,
``[startup.*.context]``, ``[compress.prompts]``) are dynamic matrices, not ``config set``
targets, and stay as hand-rolled readers in :mod:`config` — a deferred follow-up.

Reading real config stays in :mod:`config`, which is deliberately *tolerant* (a malformed
or ill-typed file falls back to defaults, never raises). This model is the schema and the
validator for writes; :func:`load` offers a typed read for callers that want one.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from generic_ml_wrapper.common import i18n, paths

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic.fields import FieldInfo

_LOG_LEVELS = ("debug", "info", "warning", "error")


class _Section(BaseModel):
    """Base for a config section: ignore unknown keys so structural tables don't clash."""

    model_config = ConfigDict(extra="ignore")


class ClientSettings(_Section):
    """The ``[client]`` section."""

    default: Annotated[str, Field(description="setting.client.default")] = "claude"
    # Per-client launch arguments, keyed by client name. A table rather than a scalar
    # because the arguments only mean anything to the client they were written for —
    # a claude flag handed to codex is an error, and the config outlives the choice of
    # client. TOML accepts either shape for this and both land here identically:
    #     [client]           args = { claude = "--foo" }
    #     [client.args]      claude = "--foo"
    # The key stays two levels (``client.args``) so lookup, help and validation need no
    # special case; ``config set`` addresses an entry by putting the client in the value
    # (``client.args claude="--foo"``) rather than in the key.
    args: Annotated[dict[str, str], Field(description="setting.client.args")] = {}


class LanguageSettings(_Section):
    """The ``[language]`` section."""

    code: Annotated[
        str | None,
        Field(description="setting.language.code"),
    ] = None


class ProfileSettings(_Section):
    """The ``[profile]`` section."""

    default_role: Annotated[str, Field(description="setting.profile.default_role")] = "default"
    default_environment: Annotated[
        str, Field(description="setting.profile.default_environment")
    ] = "work"


class LoggingSettings(_Section):
    """The ``[logging]`` section."""

    level: Annotated[
        Literal["debug", "info", "warning", "error"],
        Field(description="setting.logging.level"),
    ] = "warning"
    to_file: Annotated[
        bool,
        Field(description="setting.logging.to_file"),
    ] = True
    max_bytes: Annotated[
        int,
        Field(gt=0, description="setting.logging.max_bytes"),
    ] = 1_048_576
    backup_count: Annotated[
        int,
        Field(ge=0, description="setting.logging.backup_count"),
    ] = 5


class CompanionSettings(_Section):
    """The ``[companion]`` section."""

    persona: Annotated[str | None, Field(description="setting.companion.persona")] = None
    name: Annotated[
        str | None,
        Field(description="setting.companion.name"),
    ] = None


class TranscriptSettings(_Section):
    """The ``[transcript]`` section."""

    enabled: Annotated[bool, Field(description="setting.transcript.enabled")] = False
    root: Annotated[str | None, Field(description="setting.transcript.root")] = None


class CompressSettings(_Section):
    """The scalar keys of the ``[compress]`` section (``prompts`` stays hand-rolled)."""

    adapter: Annotated[str, Field(description="setting.compress.adapter")] = "cursor"
    model: Annotated[str, Field(description="setting.compress.model")] = "gpt-5.4"
    effort: Annotated[str, Field(description="setting.compress.effort")] = "low"


class HintsSettings(_Section):
    """The ``[hints]`` section: the suppressible exit-receipt tips."""

    show: Annotated[bool, Field(description="setting.hints.show")] = True


class AmbientSettings(_Section):
    """The ``[ambient]`` section: optional in-session context injections."""

    capability_card: Annotated[
        bool,
        Field(description="setting.ambient.capability_card"),
    ] = False


class GmlwSettings(BaseSettings):
    """The typed, TOML-backed source of truth for every settable scalar key."""

    model_config = SettingsConfigDict(extra="ignore")

    client: ClientSettings = ClientSettings()
    language: LanguageSettings = LanguageSettings()
    profile: ProfileSettings = ProfileSettings()
    logging: LoggingSettings = LoggingSettings()
    companion: CompanionSettings = CompanionSettings()
    transcript: TranscriptSettings = TranscriptSettings()
    compress: CompressSettings = CompressSettings()
    hints: HintsSettings = HintsSettings()
    ambient: AmbientSettings = AmbientSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Take values only from explicit init kwargs — env/dotenv/secrets must not leak in.

        The TOML file is fed via :func:`load` (``model_validate``); config's own reads stay
        in :mod:`config`. Suppressing the ambient sources keeps ``GmlwSettings()`` equal to
        the pure schema defaults.
        """
        # The signature is fixed by pydantic-settings; we deliberately drop every ambient
        # source (env/dotenv/secrets) and keep only explicit init kwargs.
        _ = (settings_cls, env_settings, dotenv_settings, file_secret_settings)
        return (init_settings,)


# The sections in declared order: (dotted prefix, model class). Registry rows and lookups
# walk these so a new key is added in exactly one place — its Field on the section model.
_SECTIONS: tuple[tuple[str, type[_Section]], ...] = (
    ("client", ClientSettings),
    ("language", LanguageSettings),
    ("profile", ProfileSettings),
    ("logging", LoggingSettings),
    ("companion", CompanionSettings),
    ("transcript", TranscriptSettings),
    ("compress", CompressSettings),
    ("hints", HintsSettings),
    ("ambient", AmbientSettings),
)


class UnknownSettingError(KeyError):
    """Raised when a dotted key is not a registered setting."""

    def __init__(self, key: str) -> None:
        """Record the offending key.

        Args:
            key: The unknown dotted key.
        """
        self.key = key
        super().__init__(key)

    def __str__(self) -> str:
        """Render a plain, un-repr'd message (KeyError would quote it)."""
        return f"unknown setting {self.key!r}"


class InvalidSettingValueError(ValueError):
    """Raised when a value is not valid for a setting (bad type or not an allowed value)."""

    def __init__(self, key: str, value: str, choices: tuple[str, ...] | None) -> None:
        """Record the rejected value and any allowed set.

        Args:
            key: The dotted key being set.
            value: The rejected raw value.
            choices: The allowed values, or ``None`` when the constraint is a type.
        """
        self.key = key
        self.value = value
        self.choices = choices
        allowed = f" (allowed: {', '.join(choices)})" if choices else ""
        super().__init__(f"invalid value {value!r} for {key}{allowed}")


@dataclass(frozen=True)
class SettingRow:
    """One registered setting's metadata, for rendering help and ``config list``.

    Attributes:
        key: The dotted key (e.g. ``profile.default_role``).
        type_name: A short type label (``str``/``bool``/``choice``/``str?``).
        default: The schema default.
        choices: The allowed values, or ``None`` when unconstrained.
        description: A one-line description.
    """

    key: str
    type_name: str
    default: object
    choices: tuple[str, ...] | None
    description: str


def _field(key: str) -> FieldInfo:
    """Return the ``FieldInfo`` for a dotted key, or raise :class:`UnknownSettingError`."""
    for prefix, model in _SECTIONS:
        if not key.startswith(f"{prefix}."):
            continue
        name = key[len(prefix) + 1 :]
        field = model.model_fields.get(name)
        if field is not None:
            return field
    raise UnknownSettingError(key)


def _choices(field: FieldInfo) -> tuple[str, ...] | None:
    """Return a field's allowed values when it is a ``Literal``, else ``None``."""
    if get_origin(field.annotation) is Literal:
        return tuple(str(arg) for arg in get_args(field.annotation))
    return None


def _is_optional_str(field: FieldInfo) -> bool:
    """Report whether a field is ``str | None``."""
    return type(None) in get_args(field.annotation)


def _is_table(field: FieldInfo) -> bool:
    """Report whether a field holds a ``dict[str, str]`` (a TOML table of entries)."""
    return get_origin(field.annotation) is dict


def _type_name(field: FieldInfo) -> str:
    """Return a short type label for a field."""
    if _choices(field) is not None:
        return "choice"
    if field.annotation is bool:
        return "bool"
    if _is_table(field):
        return "table"
    if _is_optional_str(field):
        return "str?"
    return "str"


def is_table(key: str) -> bool:
    """Whether a setting holds a table of entries rather than a single value.

    A table key is set one entry at a time (see :func:`parse_entry`) and merged into
    whatever the file already holds, so setting one entry never drops the others.

    Args:
        key: The dotted key.

    Returns:
        ``True`` if the setting is a table.

    Raises:
        UnknownSettingError: If the key is not registered.
    """
    return _is_table(_field(key))


def parse_entry(key: str, raw: str) -> tuple[str, str | None]:
    """Split a table setting's ``entry=value`` argument into its two halves.

    Table settings are addressed as ``config set client.args claude="--foo"``: the entry
    name rides in the *value*, not the key, so the dotted key stays two levels and every
    other part of the registry (lookup, help, validation) needs no special case.

    An empty right-hand side (``claude=``) clears that one entry rather than setting it
    to the empty string — the same "empty clears" convention optional scalars use.

    Args:
        key: The dotted key being set.
        raw: The ``entry=value`` argument as typed.

    Returns:
        The entry name and its value, or ``None`` as the value to clear the entry.

    Raises:
        InvalidSettingValueError: If ``raw`` has no ``=``, or an empty entry name.
    """
    name, separator, value = raw.partition("=")
    if not separator or not name.strip():
        raise InvalidSettingValueError(key, raw, None)
    return name.strip(), value or None


def keys() -> tuple[str, ...]:
    """Return every registered dotted key, in declared order."""
    return tuple(f"{prefix}.{name}" for prefix, model in _SECTIONS for name in model.model_fields)


def registry_rows() -> list[SettingRow]:
    """Return metadata for every registered setting, in declared order.

    Returns:
        One :class:`SettingRow` per key — the single thing help and ``config list`` render.
    """
    rows: list[SettingRow] = []
    for prefix, model in _SECTIONS:
        for name, field in model.model_fields.items():
            rows.append(
                SettingRow(
                    key=f"{prefix}.{name}",
                    type_name=_type_name(field),
                    default=field.get_default(),
                    choices=_choices(field),
                    # A Field's `description` holds the *catalogue key*, not the text: a
                    # model's fields are evaluated at import time, long before the active
                    # localiser exists, so the sentence cannot live there. Resolving here
                    # — at render time — is what lets `config list` speak French.
                    description=i18n.t(field.description) if field.description else "",
                )
            )
    return rows


def default_for(key: str) -> object:
    """Return the schema default for a dotted key (raises if unknown)."""
    return _field(key).get_default()


def choices_for(key: str) -> tuple[str, ...] | None:
    """Return a key's allowed values, or ``None`` when unconstrained (raises if unknown)."""
    return _choices(_field(key))


_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off"})


def coerce(key: str, raw: str) -> object:
    """Validate and coerce a raw string value for a setting, ready to persist.

    Args:
        key: The dotted key being set.
        raw: The raw value as typed on the command line.

    Returns:
        The coerced value (``str``/``bool``/``None``).

    Raises:
        UnknownSettingError: If the key is not registered.
        InvalidSettingValueError: If the value is not valid for the key.
    """
    field = _field(key)
    if _is_table(field):
        # A table's persisted value is the whole merged map, which needs the file's
        # current contents — outside what coercing one raw string can know. Callers
        # branch on `is_table` and use `parse_entry` instead; reaching here is a bug.
        message = f"{key} is a table setting; set one entry with parse_entry"
        raise TypeError(message)
    choices = _choices(field)
    if field.annotation is bool:
        low = raw.strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise InvalidSettingValueError(key, raw, ("true", "false"))
    if choices is not None:
        if raw not in choices:
            raise InvalidSettingValueError(key, raw, choices)
        return raw
    if _is_optional_str(field):  # empty or "none" clears an optional key back to unset
        return None if raw == "" or raw.strip().lower() == "none" else raw
    if raw == "":
        raise InvalidSettingValueError(key, raw, None)
    return raw


def load(path: Path | None = None) -> GmlwSettings:
    """Read the config file into a typed :class:`GmlwSettings` (tolerant of a bad file).

    Args:
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The parsed settings, or all-defaults when the file is absent, unreadable, or
        carries values that fail validation — mirroring :mod:`config`'s never-raise rule.
    """
    toml_path = path or (paths.HOME / "config.toml")
    try:
        data = TomlConfigSettingsSource(GmlwSettings, toml_file=toml_path)()
    except (OSError, tomllib.TOMLDecodeError):
        return GmlwSettings()
    try:
        return GmlwSettings.model_validate(data)
    except ValidationError:
        return GmlwSettings()
