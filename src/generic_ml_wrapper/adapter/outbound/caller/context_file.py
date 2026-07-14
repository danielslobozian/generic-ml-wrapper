# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Persist a session's compiled context to a durable, inspectable file.

The exact operating context a session launches with (profile + rules + workflow) is
written per session to ``~/.gmlw/contexts/<job>/<session>.context.md`` and handed to
the client from there -- a durable provenance artifact you can inspect after the run,
instead of a temp file discarded the moment the client exits.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from generic_ml_wrapper.common import paths


def write(job: str, session: str, context: str) -> Path:
    """Write ``session``'s compiled ``context`` durably, returning the file path.

    Args:
        job: The job the session belongs to.
        session: The session id (``<job>_NNN``).
        context: The compiled operating context to persist and inject.

    Returns:
        The path to the written ``<session>.context.md`` file.
    """
    directory = paths.CONTEXTS / job
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{session}.context.md"
    # Atomic: same-dir temp + replace, so a crash mid-write can't leave a torn artifact.
    descriptor, temporary = tempfile.mkstemp(dir=directory, suffix=".tmp")
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(context)
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink()
        raise
    return path
