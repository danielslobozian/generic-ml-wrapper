# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Register a gmlw session name in codex's own session index.

Codex records every session as a rollout file under ``$CODEX_HOME/sessions`` named
after the session id it minted, and keeps an opt-in *name* registry beside it in
``session_index.jsonl`` (``{"id": ..., "thread_name": ..., "updated_at": ...}``).
``codex resume``, ``archive``, ``delete`` and ``unarchive`` all accept either the id
or a name from that registry.

That registry is the join between codex's ids and ours. Once the relay has learned
the id codex minted (see ``openai_responses.read_session_id``), writing
``thread_name = <job>_NNN`` into it means the wrapper's session name resolves in
codex itself — ``codex resume my_job_003`` works, with or without gmlw.

Two behaviours of codex's own resume shape this module:

* An **unknown** id or name does not fail — codex silently starts a *new* session.
  So :func:`knows` is a precondition for resuming, not a nicety: without it a resume
  that missed produces a fresh session wearing a resumed session's name.
* The registry is a *name* index, not a session list (a handful of entries against
  a hundred rollouts here), so a missing entry is normal and never an error.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from collections.abc import Iterator

_INDEX = "session_index.jsonl"
_SESSIONS = "sessions"


def home() -> Path:
    """The codex home directory: ``$CODEX_HOME`` when set, else ``~/.codex``."""
    override = os.environ.get("CODEX_HOME")
    return Path(override) if override else Path.home() / ".codex"


def knows(uuid: str, *, root: Path | None = None) -> bool:
    """Whether codex still has the session ``uuid`` on disk.

    The rollout file is the authority — the name registry only covers named sessions,
    and a session the user deleted leaves neither. Guards the resume path, because
    codex answers an unknown session by starting a new one rather than by failing.

    Args:
        uuid: The client-side session id to look for.
        root: The codex home to search; defaults to :func:`home`.

    Returns:
        ``True`` if a rollout file for that session exists.
    """
    sessions = (root or home()) / _SESSIONS
    if not uuid or not sessions.is_dir():
        return False
    return any(sessions.rglob(f"rollout-*-{uuid}.jsonl"))


def register(name: str, uuid: str, *, root: Path | None = None) -> bool:
    """Bind ``name`` to session ``uuid`` in codex's name registry.

    Rewrites the registry with any prior entry for this id *or* this name dropped, so a
    name resolves to exactly one session and re-running a session name rebinds it
    rather than accumulating stale rows. Written via a temporary file and an atomic
    replace so a crash mid-write cannot truncate the user's registry.

    Failure is reported and swallowed: this is a convenience on top of the session's
    own record, and codex's index is the user's file, not ours. Never let it take down
    a launch.

    Args:
        name: The gmlw session name to register (``<job>_NNN``).
        uuid: The client-side session id codex minted.
        root: The codex home to write into; defaults to :func:`home`.

    Returns:
        ``True`` if the registry now binds ``name`` to ``uuid``.
    """
    base = root or home()
    index = base / _INDEX
    entry = {
        "id": uuid,
        "thread_name": name,
        "updated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    try:
        kept = [
            row for row in _rows(index) if row.get("id") != uuid and row.get("thread_name") != name
        ]
        base.mkdir(parents=True, exist_ok=True)
        temporary = index.with_suffix(".jsonl.gmlw-tmp")
        body = "".join(json.dumps(row) + "\n" for row in [*kept, entry])
        temporary.write_text(body, encoding="utf-8")
        temporary.replace(index)
    except OSError as error:
        log.warning(
            i18n.t("log.codex_index_failed", name=name, error=error),
            key="log.codex_index_failed",
        )
        return False
    return True


def _rows(index: Path) -> Iterator[dict[str, object]]:
    """Yield the registry's existing entries, skipping anything unparseable.

    A malformed line is another tool's business, not ours; dropping only the line we
    cannot read preserves every entry we can.
    """
    if not index.is_file():
        return
    for line in index.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            decoded: object = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(decoded, dict):
            yield cast("dict[str, object]", decoded)
