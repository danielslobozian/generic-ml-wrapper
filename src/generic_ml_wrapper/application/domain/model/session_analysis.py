# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What a client's own session file says about the session, from its metadata only.

Two layers. A :class:`SessionRecord` is what a client's file holds, in neutral terms: the
model calls, the user's prompts and the tool calls, each with its timings. A
:class:`SessionAnalysis` is what is shown: counts, totals and timing statistics, built
from a record by :func:`~generic_ml_wrapper.application.domain.service.session_analyzer.analyze`.

Nothing here carries content. A prompt is when it was sent and when it was answered, a
tool call is its name and timings, never what was asked or returned.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts
    from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls


@dataclass(frozen=True)
class RecordedCall:
    """One request the client made to the model.

    Attributes:
        tokens: What the request was billed for, by kind.
        by_agent: Whether an agent made it, rather than the main conversation.
        model: The model that answered, or ``None`` when the file does not say.
    """

    tokens: TokenCounts
    by_agent: bool = False
    model: str | None = None


@dataclass(frozen=True)
class RecordedPrompt:
    """One message the user sent, and when the client was done answering it.

    Attributes:
        sent_at: When the user sent it, epoch seconds.
        answered_at: When the answer ended, epoch seconds, or ``None`` when it never did
            (the session ended or was cut off first).
    """

    sent_at: float
    answered_at: float | None = None


@dataclass(frozen=True)
class RecordedToolCall:
    """One tool call, by name, with when it was made and when its result came back.

    Attributes:
        name: The tool's name, as the client calls it (``Bash``, ``exec``).
        called_at: When the model asked for it, epoch seconds.
        returned_at: When its result came back, epoch seconds, or ``None`` if it never did.
    """

    name: str
    called_at: float
    returned_at: float | None = None


@dataclass(frozen=True)
class SessionRecord:
    """A client session as its own file records it, reduced to neutral metadata.

    Attributes:
        client: The client that wrote the file (``claude``, ``codex``).
        source: The file it was read from.
        started_at: The first recorded moment, epoch seconds, or ``None`` if empty.
        ended_at: The last recorded moment, epoch seconds, or ``None`` if empty.
        calls: Every model request, the agents' included.
        prompts: The user's own messages to the main conversation, oldest first.
        tool_calls: Every tool call, the agents' included, oldest first.
    """

    client: str
    source: str
    started_at: float | None
    ended_at: float | None
    calls: tuple[RecordedCall, ...] = ()
    prompts: tuple[RecordedPrompt, ...] = ()
    tool_calls: tuple[RecordedToolCall, ...] = ()


@dataclass(frozen=True)
class SessionFile:
    """A session file a client keeps, as listed before it is read.

    Attributes:
        client: The client that wrote it.
        source: Its path.
        modified_at: When it was last written, epoch seconds.
        uuid: The client's own id for the session, or ``None`` when the file does not say.
        folder: The folder the session ran in, or ``None`` when the file does not say.
    """

    client: str
    source: str
    modified_at: float
    uuid: str | None = None
    folder: str | None = None


@dataclass(frozen=True)
class DurationStats:
    """The spread of some durations, in seconds.

    Attributes:
        count: How many durations.
        minimum: The shortest.
        median: The middle one (the mean of the two middle ones for an even count).
        mean: The average.
        maximum: The longest.
    """

    count: int
    minimum: float
    median: float
    mean: float
    maximum: float

    @classmethod
    def of(cls, durations: Sequence[float]) -> DurationStats | None:
        """The spread of ``durations``, or ``None`` when there are none."""
        if not durations:
            return None
        return cls(
            count=len(durations),
            minimum=min(durations),
            median=statistics.median(durations),
            mean=statistics.fmean(durations),
            maximum=max(durations),
        )


@dataclass(frozen=True)
class ToolTiming:
    """How long one tool's calls took, from the call to its result.

    Attributes:
        name: The tool's name.
        durations: The spread of its calls that returned.
    """

    name: str
    durations: DurationStats


@dataclass(frozen=True)
class SessionAnalysis:
    """The figures shown for one session.

    Attributes:
        client: The client that wrote the session.
        source: The file it was read from.
        session_id: The gmlw session it belongs to, or ``None`` for a session run outside gmlw.
        started_at: The first recorded moment, epoch seconds, or ``None`` if empty.
        ended_at: The last recorded moment, epoch seconds, or ``None`` if empty.
        models: The models that answered, most used first.
        main_turns: Model requests the main conversation made.
        agent_turns: Model requests agents made.
        prompts: Messages the user sent.
        tokens: Every request's tokens, by kind, the agents' included.
        answer_times: From a prompt to the end of its answer, for the prompts answered.
        tools: The tool calls, counted by name.
        tool_times: Per tool, from a call to its result, most called first. This includes
            any time the call waited for the user's approval.
    """

    client: str
    source: str
    session_id: str | None
    started_at: float | None
    ended_at: float | None
    models: tuple[str, ...]
    main_turns: int
    agent_turns: int
    prompts: int
    tokens: TokenCounts
    answer_times: DurationStats | None
    tools: ToolCalls
    tool_times: tuple[ToolTiming, ...]
