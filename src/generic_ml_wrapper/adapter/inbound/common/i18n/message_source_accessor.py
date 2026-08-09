# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.common.i18n.json_catalog_message_source import (
    JsonCatalogMessageSource,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.language_context_holder import (
    LanguageContextHolder,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.common.i18n.message_source import MessageSource


class MessageSourceAccessor:
    def __init__(self, message_source: MessageSource, language: str | None = None) -> None:
        self._message_source = message_source
        self._language = language

    def get_message(self, key: str, /, **params: object) -> str:
        language = self._language or LanguageContextHolder.get_language()
        return self._message_source.get_message(key, language, **params)

    def available_languages(self) -> list[str]:
        return self._message_source.available_languages()


_active: MessageSourceAccessor | None = None


def set_active(accessor: MessageSourceAccessor) -> None:
    global _active  # noqa: PLW0603
    _active = accessor


def get_active() -> MessageSourceAccessor:
    global _active  # noqa: PLW0603
    if _active is None:
        _active = MessageSourceAccessor(JsonCatalogMessageSource())
    return _active


def get_message(key: str, /, **params: object) -> str:
    return get_active().get_message(key, **params)
