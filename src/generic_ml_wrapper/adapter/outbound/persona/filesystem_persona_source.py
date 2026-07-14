# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``PersonaSourcePort``: personas under ``~/.gmlw/personas``."""

from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.persona_parser import parse_persona
from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.domain.model.persona import Persona

# Shared floor and any other underscored file are not selectable personas.
_FLOOR = "_floor.md"


class FilesystemPersonaSource(PersonaSourcePort):
    """Read personas from ``<root>/<name>.md``; seed the packaged defaults, missing-only.

    Reads lazily seed the packaged personas first, so the five defaults (and the
    floor) exist the moment anything asks for them, without a separate bootstrap step.
    """

    def __init__(self, root: Path) -> None:
        """Bind the source to the personas directory.

        Args:
            root: The ``~/.gmlw/personas`` directory.
        """
        self._root = root

    def seed(self) -> None:
        """Copy the packaged default personas into ``root``, never overwriting."""
        packaged = resources.files("generic_ml_wrapper").joinpath("resources", "personas")
        self._root.mkdir(parents=True, exist_ok=True)
        for entry in packaged.iterdir():
            target = self._root / entry.name
            if entry.is_file() and not target.exists():
                target.write_bytes(entry.read_bytes())

    def available(self) -> list[Persona]:
        """Return the selectable personas, sorted by name (the floor excluded)."""
        self.seed()
        personas = [
            parse_persona(path.stem, path.read_text(encoding="utf-8"))
            for path in sorted(self._root.glob("*.md"))
            if not path.name.startswith("_")
        ]
        return sorted(personas, key=lambda persona: persona.name)

    def get(self, name: str) -> Persona | None:
        """Return the named persona, or ``None`` when it does not exist."""
        self.seed()
        path = self._root / f"{name}.md"
        if not path.is_file() or name.startswith("_"):
            return None
        return parse_persona(name, path.read_text(encoding="utf-8"))

    def floor(self) -> str:
        """Return the universal floor composed beneath every persona (or ``""``)."""
        self.seed()
        path = self._root / _FLOOR
        return path.read_text(encoding="utf-8").strip() if path.is_file() else ""
