# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``RoleExamplesRepositoryPort`` over the packaged ``resources/role_examples.json``."""

from __future__ import annotations

import json
from importlib import resources
from typing import cast

from generic_ml_wrapper.application.domain.model.role import Role
from generic_ml_wrapper.application.port.outbound.role_examples_repository import (
    RoleExamplesRepositoryPort,
)

_RESOURCE = "role_examples.json"


class JsonRoleExamplesRepositoryAdapter(RoleExamplesRepositoryPort):
    """Read the offered starting-point roles from the packaged JSON file.

    The label and description hold a catalogue key rather than typed text. Nothing has to
    flag that: the localiser falls back to the key itself when the catalogue has no entry,
    so a role the user typed passes through unchanged while an offered one is translated.
    """

    def find_all(self) -> tuple[Role, ...]:
        """Return the offered roles, in the file's order.

        Returns:
            The offered roles; empty when the file is missing or unreadable, which leaves
            the caller with nothing to offer rather than a failure.
        """
        path = resources.files("generic_ml_wrapper").joinpath("resources", _RESOURCE)
        if not path.is_file():
            return ()
        try:
            raw: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ()
        if not isinstance(raw, list):
            return ()
        found: list[Role] = []
        for entry in cast("list[object]", raw):
            if not isinstance(entry, dict):
                continue
            fields = cast("dict[str, object]", entry)
            code = fields.get("code")
            if not isinstance(code, str):
                continue
            found.append(
                Role(code, str(fields.get("label", code)), str(fields.get("description", "")))
            )
        return tuple(found)
