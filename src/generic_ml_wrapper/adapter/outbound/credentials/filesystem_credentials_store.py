# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``CredentialsStorePort``: a ``0600`` ``credentials.toml`` we own."""

from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path
from typing import cast

from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort

_OWNER_READ_WRITE = 0o600


class CredentialsUnreadableError(Exception):
    """The credentials file exists but cannot be parsed as TOML.

    Overwriting it would destroy every stored secret, so the run aborts instead.
    """

    def __init__(self, path: Path) -> None:
        """Build the error with actionable guidance for ``path``."""
        self.path = path
        super().__init__(
            f"{path} is not valid TOML.\n\n"
            "It holds your stored credentials. Rewriting it would parse the corruption as\n"
            "'no secrets' and destroy them all, so the run is aborted.\n\n"
            "To fix: repair the TOML by hand, or move it aside\n"
            f"  (mv {path} {path}.bak)  and re-run `gmlw creds set` to start fresh."
        )


class FilesystemCredentialsStore(CredentialsStorePort):
    """Persist per-workflow credentials as ``[workflow]`` tables in one TOML file.

    The file is written with owner-only permissions and is never committed; it lives
    under ``~/.gmlw`` alongside the rest of the runtime state.
    """

    def __init__(self, path: Path) -> None:
        """Bind the store to its file.

        Args:
            path: The ``credentials.toml`` file this store reads and writes.
        """
        self._path = path

    def resolve(self, workflow: str) -> dict[str, str]:
        """Return a workflow's credentials as an env-var-name to value mapping."""
        table = self._load().get(workflow)
        if not isinstance(table, dict):
            return {}
        return {
            name: value
            for name, value in cast("dict[str, object]", table).items()
            if isinstance(value, str)
        }

    def set(self, workflow: str, name: str, value: str) -> None:
        """Store one credential for a workflow, replacing any prior value.

        Raises:
            CredentialsUnreadableError: If the file exists but is corrupt; it is left
                untouched rather than overwritten (which would destroy every secret).
        """
        data = self._load()
        table = data.get(workflow)
        entries = cast("dict[str, object]", table) if isinstance(table, dict) else {}
        entries[name] = value
        data[workflow] = entries
        self._write(_dump(data))

    def _write(self, text: str) -> None:
        # Atomic + owner-only from creation: mkstemp makes the temp 0600, so after the
        # replace the secrets file is 0600 with no world-readable window, and a crash
        # mid-write can't corrupt it. replace swaps the path itself, so it never writes
        # THROUGH a symlink the file might have been redirected to.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(text)
            temporary_path.replace(self._path)
        except BaseException:
            temporary_path.unlink()
            raise
        self._path.chmod(_OWNER_READ_WRITE)

    def _load(self) -> dict[str, object]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("rb") as handle:
                return tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise CredentialsUnreadableError(self._path) from error


def _dump(data: dict[str, object]) -> str:
    """Serialize ``{workflow: {name: value}}`` as TOML tables of basic strings."""
    blocks: list[str] = []
    for workflow in sorted(data):
        table = data[workflow]
        if not isinstance(table, dict):
            continue
        entries = cast("dict[str, object]", table)
        lines = [f"[{workflow}]"]
        lines += [
            f"{name} = {_basic_string(value)}"
            for name, value in sorted(entries.items())
            if isinstance(value, str)
        ]
        if len(lines) > 1:
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n" if blocks else ""


def _basic_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'
