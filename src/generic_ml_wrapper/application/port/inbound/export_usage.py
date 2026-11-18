# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for reporting a job's recorded usage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole

if TYPE_CHECKING:
    from collections.abc import Sequence

    from generic_ml_wrapper.application.domain.model.incident import Incident


# The ``cache_*_tokens`` fields carry ``# nosemgrep``: they count a model's tokens, not
# secrets, and the scanner's hard-coded-token rule matches on the name alone.
@dataclass(frozen=True)
class TurnRow:
    """One metered turn, for the per-turn table.

    Attributes:
        timestamp: The turn's wall-clock time (epoch seconds), or ``0.0``.
        model: The model that served the turn.
        duration_s: How long the turn took, in seconds.
        input_tokens: Fresh prompt tokens.
        output_tokens: Completion tokens.
        cache_read_tokens: Prompt tokens read back from the cache.
        cache_write_tokens: Prompt tokens written to the cache.
        session_id: The session the turn belongs to.
        turn_id: The provider's id for the turn, or ``None``.
        role: Whether the main conversation or an agent made the turn.
        agent: The agent's name when the client gives one, else ``None``.
        caused_by_agent: Whether this main-conversation turn was made only because an
            agent was started or reported back.
        tool_calls: The tools the turn called, ``{name: calls}``, most called first.
    """

    timestamp: float
    model: str
    duration_s: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int  # nosemgrep
    cache_write_tokens: int  # nosemgrep
    session_id: str
    turn_id: str | None
    role: TurnRole = TurnRole.MAIN
    agent: str | None = None
    caused_by_agent: bool = False
    tool_calls: dict[str, int] = field(default_factory=dict[str, int])


@dataclass(frozen=True)
class ModelTotal:
    """A model's totals across the job.

    Attributes:
        model: The model's name.
        calls: How many turns this model served.
        input_tokens: Total fresh prompt tokens.
        output_tokens: Total completion tokens.
        cache_read_tokens: Total prompt tokens read back from the cache.
        cache_write_tokens: Total prompt tokens written to the cache.
        duration_s: Total duration, in seconds.
    """

    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int  # nosemgrep
    cache_write_tokens: int  # nosemgrep
    duration_s: float


@dataclass(frozen=True)
class AgentTotal:
    """The totals of one side of the job: the main conversation, or one agent.

    Attributes:
        role: The main conversation or an agent.
        agent: The agent's name; ``None`` for the main conversation, and for the
            agents of a client that does not name them (they are counted together).
        calls: How many turns it made.
        input_tokens: Total fresh prompt tokens.
        output_tokens: Total completion tokens.
        cache_read_tokens: Total prompt tokens read back from the cache.
        cache_write_tokens: Total prompt tokens written to the cache.
        duration_s: Total duration, in seconds.
        caused_by_agent: Whether these are the main conversation's turns the agents
            caused, counted apart from its others.
    """

    role: TurnRole
    agent: str | None
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int  # nosemgrep
    cache_write_tokens: int  # nosemgrep
    duration_s: float
    caused_by_agent: bool = False


@dataclass(frozen=True)
class SessionTotal:
    """A session's totals, and its cost as its client reported it.

    Attributes:
        session_id: The session's human-readable id.
        calls: How many metered turns it made.
        input_tokens: Total fresh prompt tokens.
        output_tokens: Total completion tokens.
        cache_read_tokens: Total prompt tokens read back from the cache.
        cache_write_tokens: Total prompt tokens written to the cache.
        duration_s: Total duration, in seconds.
        cost_usd: The session's cumulative cost in USD, as its client reported it, or
            ``None`` when it reported none.
    """

    session_id: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int  # nosemgrep
    cache_write_tokens: int  # nosemgrep
    duration_s: float
    cost_usd: float | None


@dataclass(frozen=True)
class ToolTotal:
    """How often the job's turns called one tool.

    Attributes:
        tool: The tool's name, as the client calls it.
        calls: How many times it was called.
    """

    tool: str
    calls: int


@dataclass(frozen=True)
class UsageReport:
    """A job's recorded usage: per-turn rows, totals by model, agent, session and tool.

    Every token count is a raw integer, so a tool reading the JSON export does its own
    formatting. The report can be narrowed to some of the job's sessions; its totals are
    then those sessions' totals.

    Attributes:
        job: The job identifier.
        sessions_filter: The sessions the report was narrowed to; empty for all of them.
        turns: Every metered turn, chronological.
        models: Totals by model, sorted by model name.
        agents: Totals by agent -- the main conversation first, then each agent by
            name -- or empty when every turn was the main conversation's.
        sessions: Totals by session, sorted by session id: every session with a metered
            turn or a recorded cost.
        tools: Calls by tool, most called first.
        turn_count: The number of metered turns.
        input_tokens: The job's total fresh prompt tokens.
        output_tokens: The job's total completion tokens.
        cache_read_tokens: The job's total prompt tokens read back from the cache.
        cache_write_tokens: The job's total prompt tokens written to the cache.
        duration_s: The job's total metered duration, in seconds.
        total_usd: The job's total cost across its sessions, as their clients reported it.
        incidents: The connection incidents seen in its sessions, chronological.
    """

    job: str
    sessions_filter: tuple[str, ...] = ()
    turns: tuple[TurnRow, ...] = ()
    models: tuple[ModelTotal, ...] = ()
    agents: tuple[AgentTotal, ...] = ()
    sessions: tuple[SessionTotal, ...] = ()
    tools: tuple[ToolTotal, ...] = ()
    turn_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0  # nosemgrep
    cache_write_tokens: int = 0  # nosemgrep
    duration_s: float = 0.0
    total_usd: float = 0.0
    incidents: tuple[Incident, ...] = ()


class ExportUsage(ABC):
    """Report the usage recorded for a job."""

    @abstractmethod
    def execute(self, job: str, sessions: Sequence[str] = ()) -> UsageReport:
        """Build a job's usage report.

        Args:
            job: The job identifier.
            sessions: Narrow the report to these sessions; empty for all of them.

        Returns:
            The job's per-turn rows, its totals by model, agent, session and tool, and
            its overall totals.
        """
