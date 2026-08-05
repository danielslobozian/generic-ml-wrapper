# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Zip ``WorkflowArchivePort``: share a workflow as its steps, words, and scripts."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.archive_status import ArchiveStatus
from generic_ml_wrapper.application.port.outbound.workflow_archive import WorkflowArchivePort

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

# What a shared workflow consists of. An allowlist rather than a denylist, so a file
# nobody anticipated is left behind by default instead of travelling by default.
#: The one file that makes a folder a workflow rather than a bag of files.
_STEPS = "workflow.md"
_PORTABLE_FILES = frozenset({_STEPS, ".about.toml"})
_PORTABLE_DIR = "scripts"

# Everything else is excluded on purpose:
#   .claude/ .codex/ .cursor/  hold a pre-approved Bash permission allowlist. Shipping
#                              one would widen what a recipient's client may run
#                              without them ever being asked.
#   __pycache__/               interpreter-version-specific bytecode; junk to the
#                              recipient and often for a different Python entirely.
#   draft.md, parking-lot.md   authoring residue, which can carry the author's private
#                              working notes.


class ZipWorkflowArchiveAdapter(WorkflowArchivePort):
    """Pack and unpack workflows as zip files under an export root."""

    def __init__(self, root: Path, clock: Callable[[], datetime]) -> None:
        """Bind the archive to its export root and a clock (for the filename timestamp).

        Args:
            root: The directory exported archives are written to.
            clock: Returns "now"; injected so the timestamped filename is deterministic
                in tests.
        """
        self._root = root
        self._clock = clock

    def inspect(self, archive: Path) -> ArchiveStatus:
        """Read the archive's index and report whether it carries a workflow.

        The path is resolved the way a shell would resolve it -- a leading ``~`` means the
        user's home -- because a person typing a path into a prompt has every reason to
        expect that, and nobody above this line should have to know it.

        Only the central directory is read -- ``namelist`` does not extract anything --
        so this is cheap enough to run before every import and writes nowhere. A file
        that is not a zip at all reads as ``MISSING`` rather than ``INCOMPLETE``: the
        distinction the caller draws is "is there something to import here", and an
        unreadable file answers that the same way an absent one does.
        """
        resolved = archive.expanduser()
        if not resolved.is_file():
            return ArchiveStatus.MISSING
        try:
            with zipfile.ZipFile(resolved) as zipped:
                names = zipped.namelist()
        except (zipfile.BadZipFile, OSError):
            return ArchiveStatus.MISSING
        if any(_lands_at(name) == (_STEPS,) for name in names):
            return ArchiveStatus.COMPLETE
        return ArchiveStatus.INCOMPLETE

    def pack(self, folder: Path, slug: str) -> Path:
        """Write the folder's portable contents to ``<root>/<slug>-<timestamp>.zip``.

        Timestamped like the usage-report exporter, so exporting the same workflow twice
        keeps both rather than silently overwriting the earlier one.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._root / f"{slug}-{self._clock().strftime('%Y%m%d-%H%M%S')}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(_portable_paths(folder)):
                archive.write(path, path.relative_to(folder).as_posix())
        return target

    def unpack(self, archive: Path, destination: Path) -> None:
        """Extract the archive and keep only its portable contents.

        Extraction goes through ``zipfile.extractall``, which already neutralises path
        traversal — an entry named ``../../x`` lands inside the target as ``x``, and a
        leading ``/`` is stripped — so nothing escapes. Hand-rolled extraction is what
        would reintroduce that, which is why it is not done here.

        What the archive can still do is carry files a workflow has no business having,
        so the portable set is applied again on the way in: it is extracted to a scratch
        folder, and only the allowed paths are moved across.
        """
        archive = archive.expanduser()  # as inspect resolved it
        scratch = destination.parent / f".{destination.name}.unpacking"
        shutil.rmtree(scratch, ignore_errors=True)
        try:
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(scratch)
            destination.mkdir(parents=True, exist_ok=True)
            for path in sorted(_portable_paths(scratch)):
                landing = destination / path.relative_to(scratch)
                landing.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(landing))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


def _lands_at(name: str) -> tuple[str, ...]:
    """Where an archive entry ends up, relative to the folder it is extracted into.

    ``extractall`` neutralises traversal by dropping ``..`` and ``.`` components and any
    leading separator, so ``../../workflow.md`` lands as ``workflow.md`` while
    ``sub/workflow.md`` stays nested. Reproduced here rather than guessed at, because the
    difference decides whether :meth:`ZipWorkflowArchiveAdapter.inspect` and
    :meth:`ZipWorkflowArchiveAdapter.unpack` agree: only a top-level ``workflow.md`` is portable,
    so only a top-level one means the archive really carries a workflow.
    """
    return tuple(part for part in name.replace("\\", "/").split("/") if part not in ("", ".", ".."))


def _portable_paths(folder: Path) -> list[Path]:
    """Return the files inside ``folder`` that a shared workflow consists of."""
    found = [folder / name for name in _PORTABLE_FILES if (folder / name).is_file()]
    scripts = folder / _PORTABLE_DIR
    if scripts.is_dir():
        found += [
            path
            for path in scripts.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        ]
    return found
