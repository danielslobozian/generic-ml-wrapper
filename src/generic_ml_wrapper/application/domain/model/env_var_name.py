# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A validated environment-variable name (POSIX portable).

A ``str`` subclass validated on construction, so an invalid value can never be built
-- and, being a ``str``, it drops in wherever the raw value flowed before. Validation
happens at the boundary, so bad input fails early rather than deep in a filesystem path.
"""

from __future__ import annotations

import re

from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError

# An environment-variable name: POSIX portable (letters, digits, '_'; not a leading digit).
_PATTERN = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*\Z")


class EnvVarName(str):
    """A validated environment-variable name (POSIX portable)."""

    __slots__ = ()

    def __new__(cls, value: str) -> EnvVarName:
        """Return the validated value, or raise :class:`IdentifierError`."""
        if not _PATTERN.match(value):
            raise IdentifierError("error.identifier.env_var_name", value=value)
        return super().__new__(cls, value)
