# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DEFAULT_LANGUAGE = "en"

_current = DEFAULT_LANGUAGE


class LanguageContextHolder:
    @staticmethod
    def get_language() -> str:
        return _current

    @staticmethod
    def set_language(language: str) -> None:
        global _current  # noqa: PLW0603
        _current = language
