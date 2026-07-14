# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure session naming: mint the next ``<job>_NNN`` id."""

from __future__ import annotations

import re

_SUFFIX = re.compile(r"_(\d+)$")


def next_session_id(job: str, existing_ids: list[str]) -> str:
    """Return the next sequential session id for a job.

    Ids are ``<job>_NNN`` (three-digit, 1-based). The next number is one past the
    highest existing suffix, so gaps never cause a collision.

    Args:
        job: The job identifier.
        existing_ids: The session ids already recorded for the job.

    Returns:
        The next session id, e.g. ``"JOB-1_001"``.
    """
    highest = 0
    for session_id in existing_ids:
        match = _SUFFIX.search(session_id)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{job}_{highest + 1:03d}"
