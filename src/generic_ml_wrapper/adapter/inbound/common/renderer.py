# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
    MessageSourceAccessor,
    get_active,
    get_message,
)
from generic_ml_wrapper.application.domain.model.domain_error import DomainError
from generic_ml_wrapper.application.domain.model.launch_location import (
    LaunchLocation,
    LaunchLocationProblem,
)
from generic_ml_wrapper.application.port.inbound.client_readiness import ClientReadiness
from generic_ml_wrapper.application.port.inbound.job_footprint import JobFootprint
from generic_ml_wrapper.application.port.inbound.listed_client import ListedClient
from generic_ml_wrapper.application.port.inbound.session_footprint import SessionFootprint
from generic_ml_wrapper.application.port.inbound.session_summary import SessionSummary
from generic_ml_wrapper.application.port.inbound.set_outcome import SetOutcome
from generic_ml_wrapper.application.wiring.composition import (
    build_list_supported_clients,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo


def format_session_usage(
    session: SessionSummary, message_source: MessageSourceAccessor | None = None
) -> str:
    """Render one session's usage — or the word for "nothing happened here".

    A session with no turns is named rather than shown as ``0 turn(s) $0.00``: it is the
    one a user is scanning the list to find, and a word catches the eye where a row of
    zeroes reads as just more numbers.

    Args:
        session: The session to describe.
        message_source: ``None`` renders through the active language.

    Returns:
        The usage cell for this session.
    """
    message_source = message_source or get_active()
    if session.turn_count == 0:
        return message_source.get_message("sessions.usage_none")
    return message_source.get_message(
        "sessions.usage", turns=session.turn_count, cost=f"{session.cost_usd:.2f}"
    )


def format_job_footprints(
    footprints: list[JobFootprint], message_source: MessageSourceAccessor | None = None
) -> str:
    """Render what deleting these jobs would remove.

    Shown before the confirmation, so "delete them?" is answered against the actual
    contents rather than a count of names.

    Args:
        footprints: Kept in the order they were asked for, so the rows line up with the
            selection the user made.
        message_source: ``None`` renders through the active language.

    Returns:
        The block to print, without a trailing newline.
    """
    message_source = message_source or get_active()
    lines = [message_source.get_message("delete.jobs.preview", count=len(footprints)), ""]
    width = max(len(footprint.job) for footprint in footprints)
    lines += [
        message_source.get_message(
            "delete.job.row",
            job=f"{footprint.job:<{width}}",
            sessions=footprint.sessions,
            turns=footprint.turns,
            cost=f"{footprint.cost_usd:.2f}",
            contexts=footprint.contexts,
            transcripts=footprint.transcript_calls,
        )
        + format_kept_marker(footprint.removed, message_source)
        for footprint in footprints
    ]
    return "\n".join(lines)


def format_session_footprints(
    job: str,
    footprints: list[SessionFootprint],
    message_source: MessageSourceAccessor | None = None,
) -> str:
    """Render what deleting these sessions would remove, one row each.

    Args:
        job: Named in the heading, so the preview says which job is being pruned.
        footprints: Kept in the order they were asked for, so the rows line up with the
            selection the user made.
        message_source: ``None`` renders through the active language.

    Returns:
        The block to print, without a trailing newline.
    """
    message_source = message_source or get_active()
    lines = [
        message_source.get_message("delete.sessions.preview", count=len(footprints), job=job),
        "",
    ]
    width = max(len(footprint.session) for footprint in footprints)
    lines += [
        message_source.get_message(
            "delete.session.row",
            session=f"{footprint.session:<{width}}",
            turns=footprint.turns,
            cost=f"{footprint.cost_usd:.2f}",
            contexts=footprint.contexts,
            transcripts=footprint.transcript_calls,
        )
        + format_kept_marker(footprint.removed, message_source)
        for footprint in footprints
    ]
    return "\n".join(lines)


def format_client_guidance(
    readiness: ClientReadiness, message_source: MessageSourceAccessor | None = None
) -> str:
    """Render install and login guidance for a client that cannot launch.

    Args:
        readiness: Expected to be a not-ready verdict; a ready one renders nothing useful.
        message_source: ``None`` renders through the active language.

    Returns:
        The guidance block to print, without a trailing newline.
    """
    message_source = message_source or get_active()
    if readiness.missing is not None:
        info = readiness.missing
        lines = [
            message_source.get_message(
                "client.guidance.missing", client=repr(readiness.client), display=info.display
            ),
            message_source.get_message(
                "client.guidance.install", command=readiness.install_command
            ),
            message_source.get_message(
                "client.guidance.login", login=format_login_line(info, message_source)
            ),
        ]
        others = [name for name in readiness.installed if name != readiness.client]
        if others:
            lines.append(message_source.get_message("client.guidance.use_other", other=others[0]))
    else:
        supported = ", ".join(info.name for info in build_list_supported_clients().execute())
        lines = [
            message_source.get_message(
                "client.guidance.unsupported",
                client=repr(readiness.client),
                supported=supported,
            )
        ]
    if not readiness.installed:
        lines += ["", message_source.get_message("client.guidance.none_installed")]
        commands = readiness.catalogue_install_commands
        width = max((len(name) for name, _ in commands), default=0)
        lines += [f"  {name:<{width}}  {command}" for name, command in commands]
        lines.append(message_source.get_message("client.guidance.then_login"))
    return "\n".join(lines)


def format_client_version(status: ListedClient, message_source: MessageSourceAccessor) -> str:
    """The installed version, or a localised stand-in when the client is absent or its
    version could not be read.
    """
    if not status.installed:
        return message_source.get_message("clients.not_installed")
    return status.version or message_source.get_message("clients.version_unknown")


def format_setting_value(value: object, message_source: MessageSourceAccessor) -> str:
    """A localised ``(unset)`` for ``None``, and lower-case ``true``/``false`` for
    booleans so the display matches what the config file accepts back.
    """
    if value is None:
        return message_source.get_message("config.unset")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def format_set_outcome(
    outcome: SetOutcome, message_source: MessageSourceAccessor | None = None
) -> str:
    """Render the summary line for a ``config set``.

    Args:
        outcome: What the write decided.
        message_source: ``None`` renders through the active language.

    Returns:
        One of three lines — unchanged, cleared, or changed — each naming the old value
        so the write is never silent about what it replaced.
    """
    message_source = message_source or get_active()
    if not outcome.changed:
        value = format_setting_value(outcome.new, message_source)
        return message_source.get_message("config.set_unchanged", key=outcome.key, value=value)
    if outcome.new is None:
        return message_source.get_message(
            "config.set_cleared",
            key=outcome.key,
            old=format_setting_value(outcome.old, message_source),
        )
    return message_source.get_message(
        "config.set_changed",
        key=outcome.key,
        new=format_setting_value(outcome.new, message_source),
        old=format_setting_value(outcome.old, message_source),
    )


def render_error(error: Exception) -> str:
    if isinstance(error, DomainError):
        return get_message(error.catalogue_key, **error.params)
    return get_message("error.generic", error=error)


def format_token_counts(
    input_tokens: int, output_tokens: int, cache_tokens: int, message_source: MessageSourceAccessor
) -> str:
    """Args:
        input_tokens: The turn's input count.
        output_tokens: The turn's output count.
        cache_tokens: Omitted from the cell entirely when zero, rather than shown as a
            nought.
        message_source: The message source to render through.

    Returns:
        The cell, laid out by the ``usage.tokens`` catalogue entry — the arrangement is
        the translation's, not this function's.
    """
    cache = message_source.get_message("usage.cache", cache=cache_tokens) if cache_tokens else ""
    return message_source.get_message(
        "usage.tokens", input=input_tokens, cache=cache, output=output_tokens
    )


def format_kept_marker(removed: bool, message_source: MessageSourceAccessor) -> str:
    """Render the tail a footprint row carries when the thing was not removed.

    Returns:
        Empty when it was removed — which is every row on a preview, since nothing has
        gone yet.
    """
    return "" if removed else message_source.get_message("delete.row.kept")


def format_login_line(info: ClientInfo, message_source: MessageSourceAccessor) -> str:
    """The command itself is never translated -- it is something the user types. Only the
    note beside it is prose, so only the note goes through the catalogue. Rendered here
    rather than on :class:`ClientInfo`: the type carries the command and the key, and
    turning a key into a sentence needs a language, which the domain does not have.
    """
    if not info.login_hint:
        return info.login
    return f"{info.login}   ({message_source.get_message(info.login_hint)})"


def render_launch_location(location: LaunchLocation) -> bool:
    """Print what is wrong with where the run would happen, and say whether to go on.

    The verdict is the application's; naming the folder to the user is this side's.
    """
    if location.usable:
        return True
    if location.problem is LaunchLocationProblem.CURRENT_GONE:
        print(get_message("preflight.cwd_gone"), file=sys.stderr)
    else:
        print(get_message("preflight.resume_cwd_gone", cwd=location.folder), file=sys.stderr)
    return False


def get_farewell() -> str:
    return get_message("farewell")
