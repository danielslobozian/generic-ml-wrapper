# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from importlib import resources
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.adapter.inbound.common.i18n.message_source import MessageSource

if TYPE_CHECKING:
    from importlib.abc import Traversable

CATALOG_FOLDER = "i18n"
CATALOG_SUFFIX = ".json"


class JsonCatalogMessageSource(MessageSource):
    def __init__(self) -> None:
        folder = resources.files("generic_ml_wrapper").joinpath("resources", CATALOG_FOLDER)
        self._catalogs = {
            entry.name.removesuffix(CATALOG_SUFFIX): self._read_catalog(entry)
            for entry in folder.iterdir()
            if entry.is_file() and entry.name.endswith(CATALOG_SUFFIX)
        }

    def get_message(self, key: str, language: str, /, **params: object) -> str:
        catalog = self._catalogs.get(language, {})
        template = catalog.get(key, key)
        if not params:
            return template
        try:
            return template.format(**params)
        except (KeyError, IndexError, ValueError):
            return template

    def available_languages(self) -> list[str]:
        return sorted(self._catalogs)

    @staticmethod
    def _read_catalog(path: Traversable) -> dict[str, str]:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return {str(key): str(value) for key, value in cast("dict[object, object]", raw).items()}
