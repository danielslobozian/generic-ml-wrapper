# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A validated workflow name (lowercase letters/digits and ``-``).

A ``str`` subclass validated on construction, so an invalid value can never be built
-- and, being a ``str``, it drops in wherever the raw value flowed before. Validation
happens at the boundary, so bad input fails early rather than deep in a filesystem path.
"""

from __future__ import annotations

import re

from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError

# A workflow name is lowercase kebab: the same rule new_workflow used, now shared.
_PATTERN = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")


class WorkflowName(str):
    """A validated workflow name (lowercase letters/digits and ``-``)."""

    __slots__ = ()

    def __new__(cls, value: str) -> WorkflowName:
        """Return the validated value, or raise :class:`IdentifierError`."""
        if not _PATTERN.match(value):
            raise IdentifierError("error.identifier.workflow_name", value=value)
        return super().__new__(cls, value)
