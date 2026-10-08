# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What gmlw says around an attachment it delivers into a session.

An attachment knows nothing about gmlw, nor where it is stored: its files point at each
other by paths relative to its own folder. So gmlw introduces it with one paragraph of
its own -- which attachment, which version, which folder -- ahead of the main file, which
follows as written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.attachment import Attachment


def attachment_section(attachment: Attachment, folder: str, main: str) -> str:
    """The attachment's section of the startup context: gmlw's introduction, then the text.

    Args:
        attachment: The stored version the session runs with.
        folder: That version's folder, as an absolute path.
        main: Its main file's text.

    Returns:
        The section.
    """
    intro = (
        f"## Attachment: {attachment.name} {attachment.version}\n\n"
        f"This session runs with the attachment {attachment.name} {attachment.version}. "
        f"Its files are in {folder}. Paths in the text below are relative to that folder: "
        "read a file there when the text sends you to it, not before. Never write into "
        "that folder; it is read-only, and work you produce belongs in the current one."
    )
    return f"{intro}\n\n{main.strip()}"


def attachment_kickoff(attachment: Attachment, job: str) -> str:
    """The opening message of a session that runs with an attachment.

    Args:
        attachment: The stored version the session runs with.
        job: The job the session runs on.

    Returns:
        The opening message.
    """
    return (
        f"This session on {job} runs with the attachment {attachment.name} "
        f"{attachment.version}. Begin as its text says."
    )
