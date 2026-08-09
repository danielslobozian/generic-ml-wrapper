# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from abc import ABC, abstractmethod


class MessageSource(ABC):
    @abstractmethod
    def get_message(self, key: str, language: str, /, **params: object) -> str: ...

    @abstractmethod
    def available_languages(self) -> list[str]: ...
