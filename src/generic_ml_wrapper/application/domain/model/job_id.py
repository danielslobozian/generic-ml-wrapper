# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A validated job identifier (a safe single path segment).

A ``str`` subclass validated on construction, so an invalid value can never be built
-- and, being a ``str``, it drops in wherever the raw value flowed before. Validation
happens at the boundary, so bad input fails early rather than deep in a filesystem path.
"""

from __future__ import annotations

import re

from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError

# A job id is a single safe path segment: letters, digits, '-' and '_', starting
# with a letter or digit, at most 64 chars. No '.', '/', '\\', or NUL -- so no
# '..' traversal, no absolute path, no separator can reach a filesystem path.
_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class JobId(str):
    """A validated job identifier (a safe single path segment)."""

    __slots__ = ()

    def __new__(cls, value: str) -> JobId:
        """Return the validated value, or raise :class:`IdentifierError`."""
        if not _PATTERN.match(value):
            raise IdentifierError("error.identifier.job_id", value=value)
        return super().__new__(cls, value)
