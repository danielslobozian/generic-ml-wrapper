# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from generic_ml_wrapper.adapter.inbound.common.i18n.language_context_holder import (
    DEFAULT_LANGUAGE,
    LanguageContextHolder,
)

LANGUAGE_SETTING_KEY = "language.code"


class LanguageChangeInterceptor:
    @staticmethod
    def after_setting_written(key: str, value: str | None) -> bool:
        if key != LANGUAGE_SETTING_KEY:
            return False
        language = value or DEFAULT_LANGUAGE
        if language == LanguageContextHolder.get_language():
            return False
        LanguageContextHolder.set_language(language)
        return True
