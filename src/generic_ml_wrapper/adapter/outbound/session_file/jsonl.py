# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The JSON-lines plumbing both clients' session files share."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

JsonObject = dict[str, object]


def records(path: Path) -> Iterator[JsonObject]:
    """Each JSON object in the file at ``path``, one per line; other lines are skipped.

    A session file is appended to while its session runs, so its last line can be half
    written. That line, and any other that is not a JSON object, is skipped rather than
    failing the whole file.
    """
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                record: object = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield cast("JsonObject", record)


def field(record: object, *keys: str) -> object:
    """The value under ``keys`` in nested objects, or ``None`` where any level is missing."""
    value = record
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = cast("JsonObject", value).get(key)
    return value


def text(record: object, *keys: str) -> str | None:
    """The string under ``keys``, or ``None`` when absent or not a string."""
    value = field(record, *keys)
    return value if isinstance(value, str) else None


def count(record: object, *keys: str) -> int:
    """The token count under ``keys``, or 0 when absent or not a whole number."""
    value = field(record, *keys)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def epoch(record: object, *keys: str) -> float | None:
    """The ISO 8601 timestamp under ``keys`` as epoch seconds, or ``None`` if unreadable."""
    stamp = text(record, *keys)
    if stamp is None:
        return None
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return moment.timestamp() if moment.tzinfo is not None else None
