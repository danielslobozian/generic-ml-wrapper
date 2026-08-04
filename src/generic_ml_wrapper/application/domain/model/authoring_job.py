# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The one job name the system chooses for itself.

Authoring a workflow is an ordinary job in every respect that the ledger cares about:
it is a name, it accumulates sessions, and its spend is metered like any other. What
makes it different is only that *the system* picks the name rather than the user, so it
is the one job a listing can hide without hiding something the user asked for.

Both sides of that arrangement import this name -- the authoring use cases, which run
under it, and the job listing, which leaves it out. Nothing else about a job is special:
there is no kind, no second table, and no rule about who may hold which name.
"""

from __future__ import annotations

from typing import Final

from generic_ml_wrapper.application.domain.model.job_id import JobId


class AuthoringJob:
    """The job that workflow authoring and editing sessions run under."""

    NAME: Final = JobId("create-workflow")
