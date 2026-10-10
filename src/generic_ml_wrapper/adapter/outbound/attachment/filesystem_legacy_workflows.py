# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``LegacyWorkflowsPort``: an older gmlw's ``~/.gmlw/workflows/<name>/`` folders.

Each became one folder with a ``workflow.md`` beside its own files. As an attachment it is
that folder at ``1.0.0``, with ``workflow.md`` as its main file and the old shared base
put in front of it, so it behaves as it did when gmlw added that base itself.

What goes in is what the workflow may read. Left out: authoring leftovers (``draft.md``,
``parking-lot.md``, ``*.bak*`` copies), interpreter caches, and the clients' own
permission folders, which would widen what a recipient's client may run without asking.
"""

from __future__ import annotations

import tempfile
import tomllib
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

import tomlkit
from tomlkit.exceptions import ParseError

from generic_ml_wrapper.application.domain.service.attachment_manifest import MANIFEST
from generic_ml_wrapper.application.port.outbound.legacy_workflows import LegacyWorkflowsPort

if TYPE_CHECKING:
    from collections.abc import Generator

_MAIN = "workflow.md"
_ABOUT = ".about.toml"
_SHARED = "_common"
_BASE = "base.md"
# gmlw's own: the shared base, and the old authoring workflow workflow-creator replaces.
_OWN = frozenset({_SHARED, "create-workflow"})
_LEFT_OUT_FILES = frozenset({"draft.md", "parking-lot.md", _ABOUT})
_LEFT_OUT_DIRS = frozenset({"__pycache__", ".claude", ".codex", ".cursor", ".git"})
_MARKER = "workflows-migrated"


class FilesystemLegacyWorkflows(LegacyWorkflowsPort):
    """Read the old folder, never write to it; remember in ``state/`` that it ran."""

    def __init__(self, root: Path, state: Path, config_file: Path) -> None:
        """Bind to the old folder, the state folder and the config file.

        Args:
            root: The old ``~/.gmlw/workflows`` folder.
            state: Where the "already migrated" marker is kept.
            config_file: ``~/.gmlw/config.toml``.
        """
        self._root = root
        self._state = state
        self._config = config_file

    def migrated(self) -> bool:
        """Whether the marker is there."""
        return (self._state / _MARKER).exists()

    def mark_migrated(self) -> None:
        """Write the marker."""
        self._state.mkdir(parents=True, exist_ok=True)
        (self._state / _MARKER).write_text("1\n", encoding="utf-8")

    def folder(self) -> Path | None:
        """The old folder, when it exists."""
        return self._root if self._root.is_dir() else None

    def names(self) -> list[str]:
        """Each folder holding a ``workflow.md``, gmlw's own left out."""
        if not self._root.is_dir():
            return []
        return sorted(
            entry.name
            for entry in self._root.iterdir()
            if entry.is_dir() and entry.name not in _OWN and (entry / _MAIN).is_file()
        )

    @contextmanager
    def zipped(self, name: str) -> Generator[Path]:
        """Zip the folder's files with a manifest at ``1.0.0`` and the base in front."""
        folder = self._root / name
        main = (folder / _MAIN).read_text(encoding="utf-8")
        base = self._read(self._root / _SHARED / _BASE)
        with tempfile.TemporaryDirectory(prefix="gmlw-legacy-") as scratch:
            target = Path(scratch) / f"{name}.zip"
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(MANIFEST, _manifest(name, _description(folder / _ABOUT)))
                archive.writestr(_MAIN, f"{base}\n\n\n{main.strip()}\n" if base else main)
                for path in sorted(_carried(folder)):
                    relative = path.relative_to(folder).as_posix()
                    if relative != _MAIN:
                        archive.write(path, relative)
            yield target

    def rewrite_config(self) -> bool:
        """Move ``[startup.workflow]`` to ``[startup.attachment]``, drop the rest.

        ``[startup.authoring]`` and the per-workflow ``base``/``steps`` keys go; an
        interceptor bound to ``workflow`` is bound to ``attachment``. Comments and
        every other key stay as written.
        """
        if not self._config.is_file():
            return False
        text = self._config.read_text(encoding="utf-8")
        try:
            document = tomlkit.parse(text)
        except ParseError:
            return False  # a broken config is reported where it is read, not here
        root = cast("dict[str, object]", document)
        changed = _rename_startup(root)
        changed = _rebind_interceptors(root) or changed
        if changed:
            self._config.write_text(tomlkit.dumps(document), encoding="utf-8")
        return changed

    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def _carried(folder: Path) -> list[Path]:
    """The files that go into the attachment."""
    carried: list[Path] = []
    for path in folder.rglob("*"):
        parts = path.relative_to(folder).parts
        if any(part in _LEFT_OUT_DIRS for part in parts) or path.is_symlink():
            continue
        if path.is_file() and path.name not in _LEFT_OUT_FILES and ".bak" not in path.name:
            carried.append(path)
    return carried


def _description(about: Path) -> str:
    """The sidecar's description (else its label), on one line."""
    try:
        data = tomllib.loads(about.read_text(encoding="utf-8")) if about.is_file() else {}
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        data = {}
    text = data.get("description") or data.get("label") or ""
    return " ".join(str(text).split())


def _manifest(name: str, description: str) -> str:
    quoted = description.replace('"', "'")
    return f'name: {name}\ndescription: "{quoted}"\nversion: 1.0.0\nmain_md_file: {_MAIN}\n'


def _rename_startup(document: dict[str, object]) -> bool:
    startup = document.get("startup")
    if not isinstance(startup, dict):
        return False
    table = cast("dict[str, object]", startup)
    changed = table.pop("authoring", None) is not None
    old = table.pop("workflow", None)
    if old is None:
        return changed
    if "attachment" not in table and isinstance(old, dict):
        context = cast("dict[str, object]", old).get("context")
        if isinstance(context, dict):
            for key in ("base", "steps"):
                cast("dict[str, object]", context).pop(key, None)
        table["attachment"] = old
    return True


def _rebind_interceptors(document: dict[str, object]) -> bool:
    interceptors = document.get("interceptors")
    if not isinstance(interceptors, list):
        return False
    changed = False
    for entry in cast("list[object]", interceptors):
        if isinstance(entry, dict) and cast("dict[str, object]", entry).get("target") == "workflow":
            cast("dict[str, object]", entry)["target"] = "attachment"
            changed = True
    return changed
