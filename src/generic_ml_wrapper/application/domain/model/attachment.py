# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The attachment value objects: a stored version of an attachment, and its version number.

An attachment is a block of specification a session can run with (see
``docs/ATTACHMENTS.md``). Its author sets the version; gmlw stores every version it is
given, never changes one, and defaults to the highest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from generic_ml_wrapper.common.errors import DomainError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from generic_ml_wrapper.application.domain.model.identifiers import AttachmentName

# Exactly three numbers, no leading zeros, ASCII digits only: "1.0.0", "2.10.3".
_VERSION = re.compile(r"\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")


class AttachmentVersionError(DomainError, ValueError):
    """Raised when a string is not a ``MAJOR.MINOR.PATCH`` version."""


@dataclass(frozen=True, order=True)
class AttachmentVersion:
    """An attachment's version: ``MAJOR.MINOR.PATCH``, compared number by number.

    Ordered as numbers, not text, so ``2.10.0`` is above ``2.9.0``.

    Attributes:
        major: The first number.
        minor: The second number.
        patch: The third number.
    """

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> AttachmentVersion:
        """Read a version as an author wrote it.

        Args:
            text: The version, e.g. ``"1.0.0"``.

        Returns:
            The version.

        Raises:
            AttachmentVersionError: If ``text`` is not exactly three numbers without
                leading zeros (``2``, ``2.1``, ``v1.0.0``, ``1.0.0-beta`` and ``1.02.0``
                are all refused).
        """
        match = _VERSION.match(text)
        if match is None:
            raise AttachmentVersionError("error.attachment.version", value=text)
        major, minor, patch = (int(part) for part in match.groups())
        return cls(major, minor, patch)

    def __str__(self) -> str:
        """The version as written: ``MAJOR.MINOR.PATCH``."""
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Attachment:
    """One stored version of an attachment.

    Attributes:
        name: The attachment's name, its folder under the store.
        version: This version.
        description: One line shown in listings, or empty.
        main_md_file: The file delivered into the context, relative to the version's folder.
        content_hash: The SHA-256 of the version's folder, recorded at import.
    """

    name: AttachmentName
    version: AttachmentVersion
    description: str
    main_md_file: str
    content_hash: str


def highest(versions: Iterable[AttachmentVersion]) -> AttachmentVersion | None:
    """The default version for a new session: the highest one.

    Args:
        versions: The versions installed for one attachment.

    Returns:
        The highest version, or ``None`` when there is none.
    """
    return max(versions, default=None)
