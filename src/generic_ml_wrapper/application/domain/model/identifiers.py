# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Validated identifier value objects.

Each is a ``str`` subclass validated on construction, so an invalid identifier can
never be built -- and, being a ``str``, it drops in wherever the raw value flowed
before. Validation happens at the boundary (the CLI constructs them from argv),
so bad input fails early with a clear message rather than deep in a filesystem path.
"""

from __future__ import annotations

import re

# A job id is a single safe path segment: letters, digits, '-' and '_', starting
# with a letter or digit, at most 64 chars. No '.', '/', '\\', or NUL -- so no
# '..' traversal, no absolute path, no separator can reach a filesystem path.
_JOB_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")

# A workflow name is lowercase kebab: the same rule new_workflow used, now shared.
_WORKFLOW_NAME = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")

# An environment-variable name: POSIX portable (letters, digits, '_'; not a leading digit).
_ENV_VAR_NAME = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*\Z")


class IdentifierError(ValueError):
    """Raised when a string is not a valid identifier of its kind."""


class JobId(str):
    """A validated job identifier (a safe single path segment)."""

    __slots__ = ()

    def __new__(cls, value: str) -> JobId:
        """Return the validated job id, or raise :class:`IdentifierError`."""
        if not _JOB_ID.match(value):
            message = (
                f"invalid job id {value!r}: allowed characters are letters, digits, "
                "'-' and '_'; it must start with a letter or digit and be at most 64 characters"
            )
            raise IdentifierError(message)
        return super().__new__(cls, value)


class WorkflowName(str):
    """A validated workflow name (lowercase letters/digits and ``-``)."""

    __slots__ = ()

    def __new__(cls, value: str) -> WorkflowName:
        """Return the validated workflow name, or raise :class:`IdentifierError`."""
        if not _WORKFLOW_NAME.match(value):
            message = (
                f"invalid workflow name {value!r}: allowed characters are lowercase "
                "letters, digits and '-'; it must start with a letter or digit"
            )
            raise IdentifierError(message)
        return super().__new__(cls, value)


class EnvVarName(str):
    """A validated environment-variable name (POSIX portable)."""

    __slots__ = ()

    def __new__(cls, value: str) -> EnvVarName:
        """Return the validated env-var name, or raise :class:`IdentifierError`."""
        if not _ENV_VAR_NAME.match(value):
            message = (
                f"invalid environment-variable name {value!r}: allowed characters are "
                "letters, digits and '_'; it must not start with a digit"
            )
            raise IdentifierError(message)
        return super().__new__(cls, value)
