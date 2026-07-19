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

from generic_ml_wrapper.common import paths

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic.fields import FieldInfo

_LOG_LEVELS = ("debug", "info", "warning", "error")


class _Section(BaseModel):
    """Base for a config section: ignore unknown keys so structural tables don't clash."""

    model_config = ConfigDict(extra="ignore")


class ClientSettings(_Section):
    """The ``[client]`` section."""

    default: Annotated[
        str, Field(description="The client gmlw wraps when --client is omitted.")
    ] = "claude"


class LanguageSettings(_Section):
    """The ``[language]`` section."""

    code: Annotated[
        str | None,
        Field(description="The language gmlw speaks to you (unset → $LANG, then English)."),
    ] = None


class ProfileSettings(_Section):
    """The ``[profile]`` section."""

    default_role: Annotated[
        str, Field(description="The role (functional hat) composed into every session.")
    ] = "default"
    default_environment: Annotated[
        str, Field(description="The environment (the place work happens) composed into a session.")
    ] = "work"


class LoggingSettings(_Section):
    """The ``[logging]`` section."""

    level: Annotated[
        Literal["debug", "info", "warning", "error"],
        Field(description="Diagnostic log verbosity (debug < info < warning < error)."),
    ] = "warning"


class CompanionSettings(_Section):
    """The ``[companion]`` section."""

    persona: Annotated[
        str | None, Field(description="The selected persona; unset leaves the companion invisible.")
    ] = None
    name: Annotated[
        str | None,
        Field(description="The name the host greeting addresses you by; unset uses the OS user."),
    ] = None


class TranscriptSettings(_Section):
    """The ``[transcript]`` section."""

    enabled: Annotated[
        bool, Field(description="Persist the per-call in/out/usage trio for each turn.")
    ] = False
    root: Annotated[
        str | None, Field(description="Override transcript root; unset uses ~/.gmlw/transcripts.")
    ] = None


class CompressSettings(_Section):
    """The scalar keys of the ``[compress]`` section (``prompts`` stays hand-rolled)."""

    adapter: Annotated[
        str, Field(description="The generic-ml-cache adapter to compress through.")
    ] = "cursor"
    model: Annotated[str, Field(description="The model to compress context with.")] = "gpt-5.4"
    effort: Annotated[str, Field(description="The reasoning effort for compression.")] = "low"


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


def _type_name(field: FieldInfo) -> str:
    """Return a short type label for a field."""
    if _choices(field) is not None:
        return "choice"
    if field.annotation is bool:
        return "bool"
    if _is_optional_str(field):
        return "str?"
    return "str"


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
                    description=field.description or "",
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
