# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import iso639


class LanguageCode:
    @staticmethod
    def is_language(code: str) -> bool:
        try:
            return iso639.Language.match(code.lower()).part1 == code.lower()
        except iso639.LanguageNotFoundError:
            return False

    @staticmethod
    def from_posix_locale(value: str | None) -> str | None:
        if not value:
            return None
        code = value.split(".")[0].split("_")[0].strip().lower()
        return code if LanguageCode.is_language(code) else None
