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

from generic_ml_wrapper.common.errors import DomainError

# A job id is a single safe path segment: letters, digits, '-' and '_', starting
# with a letter or digit, at most 64 chars. No '.', '/', '\\', or NUL -- so no
# '..' traversal, no absolute path, no separator can reach a filesystem path.
_JOB_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")

# An attachment name is lowercase kebab: it is a folder under the store, and typed at a shell.
_ATTACHMENT_NAME = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")

# A tag groups jobs (a sprint, an epic). Compared case-insensitively, so it is stored
# lowercased; '.' is allowed for versions ("v1.2"). Short, because it is shown on every row.
_TAG_NAME = re.compile(r"\A[a-z0-9][a-z0-9._-]{0,39}\Z")

# An environment-variable name: POSIX portable (letters, digits, '_'; not a leading digit).
_ENV_VAR_NAME = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*\Z")


class IdentifierError(DomainError, ValueError):
    """Raised when a string is not a valid identifier of its kind."""


class JobId(str):
    """A validated job identifier (a safe single path segment)."""

    __slots__ = ()

    def __new__(cls, value: str) -> JobId:
        """Return the validated job id, or raise :class:`IdentifierError`."""
        if not _JOB_ID.match(value):
            raise IdentifierError("error.identifier.job_id", value=value)
        return super().__new__(cls, value)


class AttachmentName(str):
    """A validated attachment name (lowercase letters/digits and ``-``)."""

    __slots__ = ()

    def __new__(cls, value: str) -> AttachmentName:
        """Return the validated attachment name, or raise :class:`IdentifierError`."""
        if not _ATTACHMENT_NAME.match(value):
            raise IdentifierError("error.identifier.attachment_name", value=value)
        return super().__new__(cls, value)


class TagName(str):
    """A validated job tag, lowercased (letters, digits, ``.``, ``_``, ``-``; up to 40)."""

    __slots__ = ()

    def __new__(cls, value: str) -> TagName:
        """Return the validated tag, lowercased, or raise :class:`IdentifierError`."""
        folded = value.strip().lower()
        if not _TAG_NAME.match(folded):
            raise IdentifierError("error.identifier.tag_name", value=value)
        return super().__new__(cls, folded)


class EnvVarName(str):
    """A validated environment-variable name (POSIX portable)."""

    __slots__ = ()

    def __new__(cls, value: str) -> EnvVarName:
        """Return the validated env-var name, or raise :class:`IdentifierError`."""
        if not _ENV_VAR_NAME.match(value):
            raise IdentifierError("error.identifier.env_var_name", value=value)
        return super().__new__(cls, value)
