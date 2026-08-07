# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The session snapshot: the small block of facts every session opens knowing.

The rest of the context is *content* — who the user is, the place's constraints, a
workflow's steps. This is the frame around it: which role and environment are in play.
At the moment a session starts there is exactly one environment, one role, one persona
and one job, so the frame is a flat set of scalars rather than anything to resolve.

Rendered as JSON rather than prose because it is data, not instruction: a client asked
"which role am I in?" should read a field, not infer from a paragraph. Kept verbatim and
uncompressed — six short scalars are not worth a compressor pass, and losing one to
paraphrase would make the frame wrong rather than merely shorter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

_HEADER = """\
## This session

The facts this session opened with. One role and one environment are active at a time; if
asks which environment, role, persona or job they are in, this is the answer.
"""


@dataclass(frozen=True)
class SessionSnapshot:
    """The active selections a session runs under.

    Every field is a plain string; an unset one renders as ``""`` rather than being
    dropped, so the block always has the same six keys and a client never has to
    handle a missing field.

    Attributes:
        user_name: The user's name (``[companion] name``), or ``""``.
        user_prefered_language: The language gmlw speaks (``[language] code``), or ``""``.
        user_environment: The active environment slug (``[profile] default_environment``).
        user_role: The active role slug (``[profile] default_role``).
        ai_persona: The selected persona (``[companion] persona``), or ``""`` when off.
        job_name: The job this session runs on; for an authoring session, the workflow.
    """

    user_name: str = ""
    user_prefered_language: str = ""
    user_environment: str = ""
    user_role: str = ""
    ai_persona: str = ""
    job_name: str = ""

    def render(self) -> str:
        """Return the snapshot as a fenced JSON block under a short header.

        Returns:
            The rendered section, ready to sit at the head of the compiled context.
        """
        body = json.dumps(
            {
                "user_name": self.user_name,
                "user_prefered_language": self.user_prefered_language,
                "user_environment": self.user_environment,
                "user_role": self.user_role,
                "ai_persona": self.ai_persona,
                "job_name": self.job_name,
            },
            indent=2,
            ensure_ascii=False,
        )
        return f"{_HEADER}\n```json\n{body}\n```"
