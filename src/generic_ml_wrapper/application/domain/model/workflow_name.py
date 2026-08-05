# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A validated workflow name (lowercase letters/digits and ``-``).

A ``str`` subclass validated on construction, so an invalid value can never be built
-- and, being a ``str``, it drops in wherever the raw value flowed before. Validation
happens at the boundary, so bad input fails early rather than deep in a filesystem path.

What an archive's filename says the workflow is called is answered here too: it is a rule
about names, and the type that owns names is the one that should own it. The text is taken
apart with string operations rather than path ones, because the domain does not name
filesystem types -- a filename arrives here as text and is treated as text.
"""

from __future__ import annotations

import re

from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError

# A workflow name is lowercase kebab: the same rule new_workflow used, now shared.
_PATTERN = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")

#: The HHMMSS half of an export stamp: ``<slug>-YYYYMMDD-HHMMSS``.
_TIME_DIGITS = 6

#: Both separators, always. A filename reaching the domain is text that may have been
#: written on either platform, and there is no path type here to ask which one is local.
_SEPARATORS = ("/", "\\")


class WorkflowName(str):
    """A validated workflow name (lowercase letters/digits and ``-``)."""

    __slots__ = ()

    def __new__(cls, value: str) -> WorkflowName:
        """Return the validated value, or raise :class:`IdentifierError`."""
        if not _PATTERN.match(value):
            raise IdentifierError("error.identifier.workflow_name", value=value)
        return super().__new__(cls, value)

    @classmethod
    def from_archive_filename(cls, filename: str) -> WorkflowName:
        """Return the workflow name an archive's filename says it carries.

        An export writes ``<slug>-YYYYMMDD-HHMMSS.zip``, but the file is one a user can
        rename, so the bare filename is taken as the intended name and validated like any
        other. A trailing export stamp is dropped when one is present.

        Args:
            filename: The archive's location as the user gave it, or just its name.

        Returns:
            The validated workflow name.

        Raises:
            WorkflowNameError: If what the filename yields is not a valid workflow name.
        """
        stem = _stem(filename)
        head, separator, tail = stem.rpartition("-")
        if separator and len(tail) == _TIME_DIGITS and tail.isdigit():  # <slug>-<date>-<time>
            stem = head.rpartition("-")[0] or head
        try:
            return cls(stem)
        except IdentifierError as error:
            raise WorkflowNameError(error.catalogue_key, **error.params) from error


def _stem(filename: str) -> str:
    """The filename without its directories or its final extension.

    Reproduces what a path type would call the *stem*: the last component, with a trailing
    ``.suffix`` removed unless the dot leads the name (``.bashrc`` is a name, not an
    extension) or ends it.
    """
    name = filename
    for separator in _SEPARATORS:
        name = name.rpartition(separator)[2]
    dot = name.rfind(".")
    if 0 < dot < len(name) - 1:
        return name[:dot]
    return name
