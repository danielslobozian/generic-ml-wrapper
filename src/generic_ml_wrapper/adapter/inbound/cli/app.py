# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The argparse command-line inbound adapter."""

from __future__ import annotations

import argparse
import contextlib
import getpass
import importlib
import json
import os
import platform
import signal
import sys
from collections.abc import Generator, Iterable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.cli.banner import banner
from generic_ml_wrapper.adapter.inbound.cli.help_topics import (
    TOPICS,
    render_topic,
    render_topic_list,
)
from generic_ml_wrapper.adapter.inbound.cli.hints import next_hint
from generic_ml_wrapper.adapter.inbound.cli.index import render_index
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import SettingsUnreadableError
from generic_ml_wrapper.adapter.outbound.credentials.filesystem_credentials_store import (
    CredentialsUnreadableError,
)
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.domain.model.attachment import (
    AttachmentError,
    AttachmentVersion,
    AttachmentVersionError,
    find,
)
from generic_ml_wrapper.application.domain.model.axis import AxisKind
from generic_ml_wrapper.application.domain.model.identifiers import (
    AttachmentName,
    EnvVarName,
    IdentifierError,
    JobId,
)
from generic_ml_wrapper.application.domain.model.incident import Incident, IncidentKind
from generic_ml_wrapper.application.domain.model.migration import (
    LegacyMigrationReport,
    MigrationReport,
    SlugMigrationReport,
)
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
from generic_ml_wrapper.application.domain.service.attachment_context import modify_request
from generic_ml_wrapper.application.port.inbound.check_client_ready import ClientReadiness
from generic_ml_wrapper.application.port.inbound.config_commands import (
    ConfigCommands,
    SetOutcome,
    SettingView,
)
from generic_ml_wrapper.application.port.inbound.create_axis import (
    AxisExistsError,
    AxisLabelError,
    CreateAxisCommand,
)
from generic_ml_wrapper.application.port.inbound.delete_jobs import JobFootprint
from generic_ml_wrapper.application.port.inbound.delete_sessions import (
    NoSuchJobError,
    NoSuchSessionError,
    SessionFootprint,
)
from generic_ml_wrapper.application.port.inbound.export_usage import UsageReport
from generic_ml_wrapper.application.port.inbound.init import InitOutcome
from generic_ml_wrapper.application.port.inbound.list_attachments import AttachmentListing
from generic_ml_wrapper.application.port.inbound.list_clients import ClientStatus
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary
from generic_ml_wrapper.application.port.inbound.list_sessions import SessionSummary
from generic_ml_wrapper.application.port.inbound.report_health import HealthReport
from generic_ml_wrapper.application.port.inbound.set_credential import SetCredentialCommand
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJobCommand,
    StartJobResult,
)
from generic_ml_wrapper.application.wiring.composition import (
    build_axis_catalog,
    build_bootstrap,
    build_check_client_ready,
    build_check_for_update,
    build_config_commands,
    build_create_axis,
    build_delete_attachment,
    build_delete_jobs,
    build_delete_sessions,
    build_diagnostics,
    build_export_attachment,
    build_export_usage,
    build_import_attachment,
    build_init,
    build_list_attachments,
    build_list_clients,
    build_list_jobs,
    build_list_launch_clients,
    build_list_personas,
    build_list_plugins,
    build_list_rules,
    build_list_sessions,
    build_localizer,
    build_migrate_layout,
    build_migrate_legacy_workflows,
    build_migrate_slugs,
    build_render_statusline,
    build_report_health,
    build_save_usage_report,
    build_set_credential,
    build_start_job,
    build_tag_jobs,
)
from generic_ml_wrapper.common import config, i18n, paths, settings_registry
from generic_ml_wrapper.common.errors import DomainError
from generic_ml_wrapper.common.log import log
from generic_ml_wrapper.common.log import set_active as set_active_diagnostics
from generic_ml_wrapper.common.spec_loader import SpecLoadError

if TYPE_CHECKING:
    # argparse does not publicly export the type ``add_subparsers`` returns; alias it once
    # (the private reference is confined here) so the parser-builder helpers can type it.
    _SubParsers = argparse._SubParsersAction[argparse.ArgumentParser]  # pyright: ignore[reportPrivateUsage]

    # Type-only: the tui adapter is imported lazily inside `_tui` (see the note there), so
    # the post-menu handler can be typed without pulling Textual in at CLI startup.
    from generic_ml_wrapper.adapter.inbound.tui.menu_app import MenuChoice, Shelf

# Set from the Clients screen, which is not a `Switcher`, so it is named here rather than
# read off one.
CLIENT_DEFAULT_KEY = "client.default"


class LocalizedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Argparse's own chrome, rendered through our catalogue.

    ``usage:``, ``positional arguments`` and ``options`` are argparse's, not ours: it
    resolves them through its own ``gettext`` domain, which our JSON catalogue cannot
    reach. Without this the help screen ends up bilingual — our command descriptions in
    the user's language, the headings above them in English.

    The two hooks below are the seams argparse gives a formatter subclass. They are
    lightly-documented internals rather than public API, so the help-rendering tests are
    what keep this honest across Python versions.
    """

    #: Argparse's English heading -> our catalogue key.
    _HEADINGS: ClassVar[dict[str, str]] = {
        "positional arguments": "cli.section.positional",
        "options": "cli.section.options",
    }

    def add_usage(
        self,
        usage: str | None,
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],  # pyright: ignore[reportPrivateUsage]
        prefix: str | None = None,
    ) -> None:
        """Render the usage line under a localised ``usage:`` prefix."""
        super().add_usage(usage, actions, groups, prefix or i18n.t("cli.section.usage"))

    def start_section(self, heading: str | None) -> None:
        """Open a section, translating argparse's own headings on the way through."""
        key = self._HEADINGS.get(heading or "")
        super().start_section(i18n.t(key) if key else heading)


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    """Add the shared ``--json`` flag to a read command's parser."""
    parser.add_argument("--json", action="store_true", help=i18n.t("cli.flag.json"))


def _add_yes_flag(parser: argparse.ArgumentParser) -> None:
    """Add the shared ``--yes`` flag to a delete command's parser."""
    parser.add_argument("--yes", action="store_true", help=i18n.t("cli.flag.yes"))


# The top-level subcommands. A first argv token that is none of these (and not a flag)
# is treated as a job name — `gmlw <job>` is shorthand for `gmlw start <job>`. Kept in
# sync with build_parser by a test.
_COMMANDS = frozenset(
    {
        "init",
        "start",
        "jobs",
        "sessions",
        "export",
        "health",
        "clients",
        "statusline",
        "tui",
        "attachment",
        "persona",
        "plugins",
        "creds",
        "config",
        "environment",
        "role",
        "help",
    }
)


# Commands whose real work lives in a sub-action; invoked without one, they show help.
_SUBACTIONS = {
    "attachment": "attachment_command",
    "persona": "persona_command",
    "plugins": "plugins_command",
    "creds": "creds_command",
    "config": "config_command",
    "environment": "environment_command",
    "role": "role_command",
}


def _incomplete_command_help(parser: argparse.ArgumentParser, args: argparse.Namespace) -> bool:
    """Print a sub-command's help when it was invoked without its action.

    Args:
        parser: The top-level parser.
        args: The parsed arguments.

    Returns:
        ``True`` when the command was incomplete and its help was printed.
    """
    dest = _SUBACTIONS.get(args.command)
    if dest is None or getattr(args, dest) is not None:
        return False
    # Re-parse as `<command> -h`; argparse prints that command's help and exits.
    with contextlib.suppress(SystemExit):
        parser.parse_args([args.command, "-h"])
    return True


def _implicit_start(argv: list[str]) -> list[str]:
    """Rewrite a bare ``gmlw <job> ...`` into ``gmlw start <job> ...`` (git-style).

    Args:
        argv: The raw arguments.

    Returns:
        ``argv`` unchanged for a known subcommand, a flag, or no args; otherwise the
        same arguments with ``start`` prepended.
    """
    if argv and argv[0] not in _COMMANDS and not argv[0].startswith("-"):
        return ["start", *argv]
    return argv


def _as_json(payload: object) -> str:
    """Render a payload as pretty-printed JSON (no trailing newline)."""
    return json.dumps(payload, indent=2)


def _version_string() -> str:
    """Return ``gmlw <version> (build <id>)``; a plain fallback if unbuilt.

    ``_build_info`` is stamped into the wheel at build time; a source checkout that was
    never built lacks it and reports ``(source, unbuilt)`` instead.

    Returns:
        The version line for ``gmlw --version``.
    """
    try:
        build_info = importlib.import_module("generic_ml_wrapper._build_info")
    except ModuleNotFoundError:
        return f"gmlw {__version__} (source, unbuilt)"
    build_id = getattr(build_info, "BUILD_ID", "unknown")
    return f"gmlw {__version__} (build {build_id})"


def build_parser() -> argparse.ArgumentParser:  # noqa: PLR0915  (declarative parser wiring)
    """Build the top-level argument parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="gmlw",
        description=banner(),
        formatter_class=LocalizedHelpFormatter,
        # argparse builds `-h` itself, with its own English text that our catalogue cannot
        # reach (it resolves through argparse's gettext domain, not ours). Declining the
        # built-in and adding the flag ourselves is what lets the whole help screen speak
        # one language instead of two.
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help=i18n.t("cli.flag.help"))
    parser.add_argument(
        "--version", action="version", version=_version_string(), help=i18n.t("cli.flag.version")
    )
    sub = parser.add_subparsers(dest="command", metavar=i18n.t("cli.metavar.command"))

    sub.add_parser(
        "init",
        help=i18n.t("cli.cmd.init"),
    )

    start = sub.add_parser("start", help=i18n.t("cli.cmd.start"))
    start.add_argument("job", nargs="?", default=None, help=i18n.t("cli.arg.job"))
    start.add_argument(
        "--client",
        default=None,
        help=i18n.t("cli.flag.client"),
    )
    start.add_argument(
        "--resume-latest",
        action="store_true",
        help=i18n.t("cli.flag.resume_latest"),
    )
    start.add_argument(
        "--attach",
        default=None,
        metavar=i18n.t("cli.metavar.attach"),
        help=i18n.t("cli.flag.attach"),
    )
    start.add_argument(
        "--client-args",
        default=None,
        help=i18n.t("cli.flag.client_args"),
    )
    start.add_argument(
        "--tag",
        action="append",
        default=None,
        help=i18n.t("cli.flag.start_tag"),
    )

    # `jobs` and `sessions` stay list-first: their `delete` sub-action is optional, so a
    # bare `gmlw jobs` still lists. Deliberately *not* in `_SUBACTIONS` — that map makes a
    # command with no action print its help, which is right for `attachment` and wrong here.
    jobs = sub.add_parser("jobs", help=i18n.t("cli.cmd.jobs"))
    _add_json_flag(jobs)
    jobs.add_argument("--tag", default=None, help=i18n.t("cli.flag.jobs_tag"))
    jobs_sub = jobs.add_subparsers(dest="jobs_command", metavar=i18n.t("cli.metavar.action"))
    jobs_delete = jobs_sub.add_parser("delete", help=i18n.t("cli.cmd.jobs_delete"))
    jobs_delete.add_argument("job", nargs="+", help=i18n.t("cli.arg.delete_jobs"))
    _add_yes_flag(jobs_delete)
    for verb in ("tag", "untag"):
        jobs_tag = jobs_sub.add_parser(verb, help=i18n.t(f"cli.cmd.jobs_{verb}"))
        jobs_tag.add_argument("job", help=i18n.t("cli.arg.job"))
        # `tags`, not `tag`: the `jobs --tag` filter already owns that destination.
        jobs_tag.add_argument(
            "tags", nargs="+", metavar=i18n.t("cli.metavar.tag"), help=i18n.t("cli.arg.tags")
        )

    sessions = sub.add_parser("sessions", help=i18n.t("cli.cmd.sessions"))
    sessions.add_argument("job", help=i18n.t("cli.arg.job"))
    _add_json_flag(sessions)
    sessions_sub = sessions.add_subparsers(
        dest="sessions_command", metavar=i18n.t("cli.metavar.action")
    )
    sessions_delete = sessions_sub.add_parser("delete", help=i18n.t("cli.cmd.sessions_delete"))
    sessions_delete.add_argument("session", nargs="+", help=i18n.t("cli.arg.delete_sessions"))
    _add_yes_flag(sessions_delete)

    export = sub.add_parser("export", help=i18n.t("cli.cmd.export"))
    export.add_argument("job", help=i18n.t("cli.arg.job"))
    _add_json_flag(export)

    health = sub.add_parser("health", help=i18n.t("cli.cmd.health"))
    health.add_argument("--days", type=int, default=7, help=i18n.t("cli.flag.health_days"))
    health.add_argument("--job", default=None, help=i18n.t("cli.flag.health_job"))
    _add_json_flag(health)

    clients = sub.add_parser("clients", help=i18n.t("cli.cmd.clients"))
    _add_json_flag(clients)

    sub.add_parser("statusline", help=i18n.t("cli.cmd.statusline"))

    sub.add_parser("tui", help=i18n.t("cli.cmd.tui"))

    attachment = sub.add_parser("attachment", help=i18n.t("cli.cmd.attachment"))
    attachment_sub = attachment.add_subparsers(
        dest="attachment_command", metavar=i18n.t("cli.metavar.action")
    )
    attachment_import = attachment_sub.add_parser(
        "import", help=i18n.t("cli.cmd.attachment_import")
    )
    attachment_import.add_argument("archive", help=i18n.t("cli.arg.attachment_archive"))
    attachment_export = attachment_sub.add_parser(
        "export", help=i18n.t("cli.cmd.attachment_export")
    )
    attachment_export.add_argument("name", help=i18n.t("cli.arg.attachment_name"))
    attachment_export.add_argument(
        "version", nargs="?", default=None, help=i18n.t("cli.arg.attachment_version_optional")
    )
    attachment_export.add_argument("--to", default=".", help=i18n.t("cli.flag.attachment_to"))
    attachment_list = attachment_sub.add_parser("list", help=i18n.t("cli.cmd.attachment_list"))
    _add_json_flag(attachment_list)
    attachment_delete = attachment_sub.add_parser(
        "delete", help=i18n.t("cli.cmd.attachment_delete")
    )
    attachment_delete.add_argument("name", help=i18n.t("cli.arg.attachment_name"))
    attachment_delete.add_argument("version", help=i18n.t("cli.arg.attachment_version"))
    _add_yes_flag(attachment_delete)

    persona = sub.add_parser("persona", help=i18n.t("cli.cmd.persona"))
    persona_sub = persona.add_subparsers(
        dest="persona_command", metavar=i18n.t("cli.metavar.action")
    )
    persona_list = persona_sub.add_parser("list", help=i18n.t("cli.cmd.persona_list"))
    _add_json_flag(persona_list)

    plugins = sub.add_parser("plugins", help=i18n.t("cli.cmd.plugins"))
    plugins_sub = plugins.add_subparsers(
        dest="plugins_command", metavar=i18n.t("cli.metavar.action")
    )
    plugins_list = plugins_sub.add_parser("list", help=i18n.t("cli.cmd.plugins_list"))
    _add_json_flag(plugins_list)

    creds = sub.add_parser("creds", help=i18n.t("cli.cmd.creds"))
    creds_sub = creds.add_subparsers(dest="creds_command", metavar=i18n.t("cli.metavar.action"))
    creds_set = creds_sub.add_parser("set", help=i18n.t("cli.cmd.creds_set"))
    creds_set.add_argument("attachment", help=i18n.t("cli.arg.creds_attachment"))
    creds_set.add_argument("name", help=i18n.t("cli.arg.creds_name"))

    _add_config_parser(sub)
    _add_axis_parsers(sub)
    _add_help_parser(sub)
    return parser


def _add_axis_parsers(sub: _SubParsers) -> None:
    """Add the ``environment`` and ``role`` commands (each with a ``new`` action)."""
    # Keyed per axis rather than interpolating a noun into one sentence: "create and
    # manage {noun}s" only pluralises in English, and French needs its own article and
    # agreement per axis. Two axes is few enough to spell out honestly.
    for command in ("environment", "role"):
        parser = sub.add_parser(command, help=i18n.t(f"cli.cmd.{command}"))
        action = parser.add_subparsers(
            dest=f"{command}_command", metavar=i18n.t("cli.metavar.action")
        )
        new = action.add_parser("new", help=i18n.t(f"cli.cmd.{command}_new"))
        new.add_argument("label", help=i18n.t("cli.arg.axis_label"))
        new.add_argument("--description", default="", help=i18n.t("cli.flag.axis_description"))
        new.add_argument(
            "--default",
            action="store_true",
            dest="make_default",
            help=i18n.t(f"cli.flag.{command}_default"),
        )


def _add_config_parser(sub: _SubParsers) -> None:
    """Add the ``config`` command (list/get/set) to the top-level subparsers."""
    config_parser = sub.add_parser("config", help=i18n.t("cli.cmd.config"))
    config_sub = config_parser.add_subparsers(
        dest="config_command", metavar=i18n.t("cli.metavar.action")
    )
    config_list = config_sub.add_parser("list", help=i18n.t("cli.cmd.config_list"))
    _add_json_flag(config_list)
    config_get = config_sub.add_parser("get", help=i18n.t("cli.cmd.config_get"))
    config_get.add_argument("key", help=i18n.t("cli.arg.config_key_example"))
    _add_json_flag(config_get)
    config_set = config_sub.add_parser("set", help=i18n.t("cli.cmd.config_set"))
    config_set.add_argument("key", help=i18n.t("cli.arg.config_key"))
    config_set.add_argument("value", help=i18n.t("cli.arg.config_value"))


def _add_help_parser(sub: _SubParsers) -> None:
    """Add the ``help`` command (topic explainers) to the top-level subparsers."""
    help_parser = sub.add_parser("help", help=i18n.t("cli.cmd.help"))
    help_parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        metavar=i18n.t("cli.metavar.topic"),
        help=i18n.t("cli.arg.help_topic", topics=", ".join(TOPICS)),
    )


def format_jobs(
    summaries: list[JobSummary], loc: i18n.Localizer | None = None, *, tag: str | None = None
) -> str:
    """Render the job summaries as human-readable lines.

    Args:
        summaries: The job summaries to render.
        loc: The localiser to render through; defaults to the active language.
        tag: The tag the list was filtered on, if any -- so an empty result says that no
            job carries it, rather than that there are no jobs at all.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not summaries:
        return loc.t("jobs.none") if tag is None else loc.t("jobs.none_tagged", tag=tag)
    lines = [loc.t("jobs.count", count=len(summaries)), ""]
    width = max(len(summary.job) for summary in summaries)
    counts = [loc.t("jobs.sessions", count=summary.session_count) for summary in summaries]
    count_width = max(len(count) for count in counts)
    lines += [
        loc.t(
            "jobs.row",
            job=f"{summary.job:<{width}}",
            sessions=f"{count:<{count_width}}",
            tags=format_tags(summary.tags),
        ).rstrip()
        for summary, count in zip(summaries, counts, strict=True)
    ]
    return "\n".join(lines)


def format_tags(tags: Sequence[str]) -> str:
    """Render tags the way every listing shows them: ``#sprint-42 #payments``."""
    return " ".join(f"#{tag}" for tag in tags)


def format_sessions(
    job: str, sessions: list[SessionSummary], loc: i18n.Localizer | None = None
) -> str:
    """Render a job's sessions as human-readable lines.

    Args:
        job: The job the sessions belong to.
        sessions: The session summaries to render.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not sessions:
        return loc.t("sessions.none", job=repr(job), start_job=job)
    lines = [loc.t("sessions.count", job=job, count=len(sessions)), ""]
    session_width = max(len(session.session_id) for session in sessions)
    client_width = max(len(session.client) for session in sessions)
    usages = [format_session_usage(session, loc) for session in sessions]
    usage_width = max(len(usage) for usage in usages)
    attached = [session.attachment or loc.t("sessions.no_attachment") for session in sessions]
    attached_width = max(len(name) for name in attached)
    for session, usage, attachment in zip(sessions, usages, attached, strict=True):
        resumable = loc.t("clients.yes") if session.resumable else loc.t("clients.no")
        lines.append(
            loc.t(
                "sessions.row",
                session=f"{session.session_id:<{session_width}}",
                date=f"{(session.created_at or '')[:16]:<16}",  # YYYY-MM-DD HH:MM (blank if unset)
                client=f"{session.client:<{client_width}}",
                resumable=f"{resumable:<3}",
                usage=f"{usage:<{usage_width}}",
                attachment=f"{attachment:<{attached_width}}",
                folder=session.cwd or loc.t("sessions.no_folder"),
            )
            + (loc.t("sessions.incidents", count=session.incidents) if session.incidents else "")
        )
    return "\n".join(lines)


def format_session_usage(session: SessionSummary, loc: i18n.Localizer | None = None) -> str:
    """Render one session's usage — or the word for "nothing happened here".

    A session with no turns is named rather than shown as ``0 turn(s) $0.00``: it is the
    one a user is scanning the list to find, and a word catches the eye where a row of
    zeroes reads as just more numbers.

    Args:
        session: The session to describe.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The usage cell for this session.
    """
    loc = loc or i18n.active()
    if session.turn_count == 0:
        return loc.t("sessions.usage_none")
    return loc.t("sessions.usage", turns=session.turn_count, cost=f"{session.cost_usd:.2f}")


def format_job_footprints(
    footprints: list[JobFootprint], loc: i18n.Localizer | None = None, *, heading: bool = True
) -> str:
    """Render what deleting these jobs would remove, or what a delete left behind.

    Shown before the confirmation, so "delete them?" is answered against the actual
    contents rather than a count of names. Reused after a delete for the rows that stayed,
    each marked, without the "this will remove" heading that no longer holds.

    Args:
        footprints: One footprint per job, in the order they were asked for.
        loc: The localiser to render through; defaults to the active language.
        heading: Whether to open with the preview's heading.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    lines = [loc.t("delete.jobs.preview", count=len(footprints)), ""] if heading else []
    width = max(len(footprint.job) for footprint in footprints)
    lines += [
        loc.t(
            "delete.job.row",
            job=f"{footprint.job:<{width}}",
            sessions=footprint.sessions,
            turns=footprint.turns,
            cost=f"{footprint.cost_usd:.2f}",
            contexts=footprint.contexts,
            transcripts=footprint.transcript_calls,
        )
        + _kept_marker(footprint.removed, loc)
        for footprint in footprints
    ]
    return "\n".join(lines)


def _kept_marker(removed: bool, loc: i18n.Localizer) -> str:
    """The tail a row carries when it did not go. Empty on a preview, where all go."""
    return "" if removed else loc.t("delete.row.kept")


def format_session_footprints(
    job: str,
    footprints: list[SessionFootprint],
    loc: i18n.Localizer | None = None,
    *,
    heading: bool = True,
) -> str:
    """Render what deleting these sessions would remove, or what a delete left behind.

    Args:
        job: The job the sessions belong to.
        footprints: One footprint per session, in the order they were asked for.
        loc: The localiser to render through; defaults to the active language.
        heading: Whether to open with the preview's heading.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    lines = (
        [loc.t("delete.sessions.preview", count=len(footprints), job=job), ""] if heading else []
    )
    width = max(len(footprint.session) for footprint in footprints)
    lines += [
        loc.t(
            "delete.session.row",
            session=f"{footprint.session:<{width}}",
            turns=footprint.turns,
            cost=f"{footprint.cost_usd:.2f}",
            contexts=footprint.contexts,
            transcripts=footprint.transcript_calls,
        )
        + _kept_marker(footprint.removed, loc)
        for footprint in footprints
    ]
    return "\n".join(lines)


def format_usage(report: UsageReport, loc: i18n.Localizer | None = None) -> str:
    """Render a job's usage report: per-turn rows, totals by model, cost, and totals.

    Args:
        report: The usage report to render.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    # A session can lose its connection before a single turn is metered; its incidents
    # are still worth showing.
    if report.turn_count == 0 and not report.session_costs and not report.incidents:
        return loc.t("usage.none", job=repr(report.job))
    width = max(
        (len(model.model) for model in report.models),
        default=len(_UNKNOWN_LABEL),
    )
    # Who made each turn, shown only once a job has agent turns to tell apart.
    who = {(a.role, a.agent): _who(a.role, a.agent, loc) for a in report.agents}
    who_width = max((len(label) for label in who.values()), default=0)
    lines = [loc.t("usage.header", job=report.job, count=report.turn_count), ""]
    for turn in report.turns:
        label = who.get((turn.role, turn.agent))
        lines.append(
            loc.t(
                "usage.turn_row",
                clock=_clock(turn.timestamp),
                model=(
                    f"{turn.model:<{width}}"
                    if label is None
                    else f"{label:<{who_width}}  {turn.model:<{width}}"
                ),
                duration=f"{turn.duration_s:>5.1f}",
                tokens=_tokens(turn.input_tokens, turn.output_tokens, turn.cache_tokens, loc),
                turn_id=turn.turn_id or "-",
            )
        )
    if report.models:
        lines += ["", loc.t("usage.totals_by_model")]
        lines += [
            loc.t(
                "usage.model_row",
                model=f"{model.model:<{width}}",
                calls=f"{model.calls:>3}",
                tokens=_tokens(model.input_tokens, model.output_tokens, model.cache_tokens, loc),
                duration=f"{model.duration_s:.1f}",
            )
            for model in report.models
        ]
    if report.agents:
        lines += ["", loc.t("usage.totals_by_agent")]
        lines += [
            loc.t(
                "usage.agent_row",
                agent=f"{who[agent.role, agent.agent]:<{who_width}}",
                calls=f"{agent.calls:>3}",
                tokens=_tokens(agent.input_tokens, agent.output_tokens, agent.cache_tokens, loc),
                duration=f"{agent.duration_s:.1f}",
            )
            for agent in report.agents
        ]
    if report.incidents:
        lost = sum(1 for i in report.incidents if i.kind is IncidentKind.CONNECTION_LOST)
        lines += [
            "",
            loc.t(
                "usage.incidents",
                count=len(report.incidents),
                lost=lost,
                cut=len(report.incidents) - lost,
            ),
        ]
        lines += [format_incident(incident, loc) for incident in report.incidents]
    if report.session_costs:
        lines += ["", loc.t("usage.cost_by_session")]
        lines += [
            loc.t("usage.cost_row", session=cost.session_id, cost=f"{cost.cost_usd:.2f}")
            for cost in report.session_costs
        ]
    lines += [
        "",
        loc.t(
            "usage.total",
            count=report.turn_count,
            tokens=_tokens(report.input_tokens, report.output_tokens, report.cache_tokens, loc),
            duration=f"{report.duration_s:.1f}",
            total=f"{report.total_usd:.2f}",
        ),
    ]
    return "\n".join(lines)


_UNKNOWN_LABEL = "(unknown)"


def _who(role: TurnRole, agent: str | None, loc: i18n.Localizer) -> str:
    """Name the side of a session a turn came from: main, the agent's name, or agent."""
    if agent is not None:
        return agent
    return loc.t("usage.role_main" if role is TurnRole.MAIN else "usage.role_agent")


def _clock(timestamp: float) -> str:
    """Render an epoch timestamp as a local ``HH:MM:SS``, or a dash when unset."""
    if timestamp <= 0:
        return "--:--:--"
    return datetime.fromtimestamp(timestamp, tz=UTC).astimezone().strftime("%H:%M:%S")


def _tokens(input_tokens: int, output_tokens: int, cache_tokens: int, loc: i18n.Localizer) -> str:
    """Render a token triple as ``  <in>(+<cache> cache)+<out> tok`` for the report."""
    cache = loc.t("usage.cache", cache=cache_tokens) if cache_tokens else ""
    return loc.t("usage.tokens", input=input_tokens, cache=cache, output=output_tokens)


def format_personas(personas: list[Persona], loc: i18n.Localizer | None = None) -> str:
    """Render the selectable personas as human-readable lines.

    Args:
        personas: The personas to render.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not personas:
        return loc.t("persona.none")
    lines = [loc.t("persona.count", count=len(personas)), ""]
    width = max(len(persona.name) for persona in personas)
    lines += [
        loc.t("persona.row", name=f"{persona.name:<{width}}", description=persona.description)
        for persona in personas
    ]
    return "\n".join(lines)


def format_attachments(listings: list[AttachmentListing], loc: i18n.Localizer | None = None) -> str:
    """Render the stored attachment versions as human-readable lines.

    Args:
        listings: The stored versions, each with whether it is intact.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not listings:
        return loc.t("attachment.none")
    lines = [loc.t("attachment.count", count=len(listings)), ""]
    name_width = max(len(item.attachment.name) for item in listings)
    version_width = max(len(str(item.attachment.version)) for item in listings)
    for item in listings:
        name = f"{item.attachment.name:<{name_width}}"
        version = f"{item.attachment.version!s:<{version_width}}"
        if item.intact:
            lines.append(
                loc.t(
                    "attachment.row",
                    name=name,
                    version=version,
                    description=item.attachment.description,
                )
            )
        else:
            lines.append(loc.t("attachment.row_invalid", name=name, version=version))
    return "\n".join(lines)


def format_plugins(plugins: list[Plugin], loc: i18n.Localizer | None = None) -> str:
    """Render the installed plugins as human-readable lines.

    Args:
        plugins: The plugins to render.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not plugins:
        return loc.t("plugins.none")
    lines = [loc.t("plugins.count", count=len(plugins)), ""]
    width = max(len(plugin.plugin_id) for plugin in plugins)
    lines += [
        loc.t("plugins.row", plugin=f"{plugin.plugin_id:<{width}}", description=plugin.description)
        for plugin in plugins
    ]
    return "\n".join(lines)


def _client_version_label(status: ClientStatus, loc: i18n.Localizer) -> str:
    """Render a client's version cell — shared by the CLI table and the TUI Clients view."""
    if not status.installed:
        return loc.t("clients.not_installed")
    return status.version or loc.t("clients.version_unknown")


def format_clients(statuses: list[ClientStatus], loc: i18n.Localizer | None = None) -> str:
    """Render the supported clients as human-readable lines: version, resume, default.

    Args:
        statuses: The client statuses to render, in catalog order.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    lines = [loc.t("clients.count", count=len(statuses)), ""]
    versions = [_client_version_label(status, loc) for status in statuses]
    name_width = max(len(status.display) for status in statuses)
    version_width = max(len(version) for version in versions)
    for status, version in zip(statuses, versions, strict=True):
        resumable = loc.t("clients.yes") if status.resumable else loc.t("clients.no")
        if status.resume_hint:  # a yes with a condition on it (codex: only once bound)
            resumable += f" ({loc.t(status.resume_hint)})"
        default = loc.t("clients.default") if status.is_default else ""
        lines.append(
            loc.t(
                "clients.row",
                client=f"{status.display:<{name_width}}",
                version=f"{version:<{version_width}}",
                resumable=resumable,
                default=default,
            )
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI, returning a clean exit code instead of dumping a traceback.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    try:
        return _dispatch(sys.argv[1:] if argv is None else argv)
    except KeyboardInterrupt:
        print(file=sys.stderr)  # a tidy newline after ^C, never a traceback
        return 130
    except Exception as error:  # noqa: BLE001  last resort: no traceback reaches the user
        print(i18n.t("error.unexpected", error=error), file=sys.stderr)
        return 1


def _render_error(error: Exception) -> str:
    """Render a caught error in the active language.

    A :class:`DomainError` carries its own catalogue key and params -- localising it is
    just reading them back. Anything else reaches here only through a bug, so it falls
    back to the generic, unlocalised shell rather than pretending to translate it.
    """
    if isinstance(error, DomainError):
        return error.localized(i18n.active())
    return i18n.t("error.generic", error=error)


#: Commands after which another program owns the terminal — a client takes it over, or
#: the TUI paints a full-screen surface. Diagnostics must not go to stderr for these:
#: stderr is that program's screen, so a line written there corrupts its display and is
#: gone on the next redraw. They go to the rolling log file only (issue #59).
_HANDOVER_COMMANDS = frozenset({"start", "tui"})
# Accepted as "yes" when confirming, in either shipped language.
_AFFIRMATIVE = frozenset({"y", "yes", "o", "oui"})


def _hands_over_the_terminal(args: argparse.Namespace) -> bool:
    """Report whether this command cedes the terminal to another program.

    Args:
        args: The parsed arguments.

    Returns:
        True when a client (or the full-screen menu) will own the screen.
    """
    # Bare `gmlw` opens the menu, the usual way in, and a job launched from it hands the
    # terminal to the client. Missing it here left stderr logging on for every session
    # started that way, so a dropped connection printed a traceback over the client.
    return args.command is None or args.command in _HANDOVER_COMMANDS


def _dispatch(resolved: list[str]) -> int:  # noqa: PLR0911, PLR0912  (a per-command dispatcher)
    # Bind the language the whole app speaks *first*: every user string and log line
    # renders through this active localiser (seeded to English until now). It has to
    # precede `build_parser`, because the parser resolves its own help text through the
    # catalogue as it is built — build it any earlier and `--help` is always English.
    i18n.set_active(build_localizer())
    parser = build_parser()
    args = parser.parse_args(_implicit_start(resolved))
    set_active_diagnostics(
        build_diagnostics(
            quiet=args.command == "statusline",
            to_stderr=not _hands_over_the_terminal(args),
        )
    )
    if _incomplete_command_help(parser, args):  # e.g. `gmlw attachment` -> show its help
        return 0
    # The init gate: on a real command (not the statusline hot path or bare help), an
    # un-initialised or legacy install (`[init] version` absent) is funnelled through the
    # forced setup before the requested command runs. `gmlw init` is exempt — it *is* the
    # setup, run by the dispatch below; bootstrapping ahead of it would seed a config that
    # init then mistook for a legacy one. Once initialised, just ensure the layout.
    if args.command not in (None, "statusline", "help"):
        needs_init = config.init_version() is None
        if needs_init and args.command != "init":
            _announce_init(build_init().execute())
        elif not needs_init:
            build_bootstrap().execute()
        # Wrap the old profile/company layout into the active environment. Runs after init
        # has persisted the environment (or reads the existing one), once per command, and
        # is a no-op once the old layout is gone — catching installs initialised before the
        # migration existed. The `init` command runs its own below (after it writes config).
        if args.command != "init":
            _announce_migration(build_migrate_layout().execute())
            _announce_slug_migration(build_migrate_slugs().execute())
            _announce_legacy_migration(build_migrate_legacy_workflows().execute())
    try:
        if args.command is None:  # bare `gmlw`: first run → init, thereafter → the index
            return _index()
        if args.command == "help":
            return _help(args)
        if args.command == "init":
            return _run_init()
        if args.command == "start":
            return _start(args)
        if args.command == "statusline":
            return _statusline()
        if args.command == "tui":
            return _tui()
        if args.command == "attachment":
            return _attachment(args)
        if args.command == "persona":
            return _persona(args)
        if args.command == "plugins":
            return _plugins(args)
        if args.command == "creds":
            return _creds(args)
        if args.command == "config":
            return _config(args)
        if args.command == "environment":
            return _axis(AxisKind.ENVIRONMENT, args.environment_command, args)
        if args.command == "role":
            return _axis(AxisKind.ROLE, args.role_command, args)
        # The delete sub-actions of the two list commands. Ahead of `_view`, which is for
        # reads: these write, and answer with an exit code rather than a rendered view.
        if args.command == "jobs" and args.jobs_command == "delete":
            return _jobs_delete(args)
        if args.command == "jobs" and args.jobs_command in ("tag", "untag"):
            return _jobs_tag(args)
        if args.command == "health":
            return _health(args)
        if args.command == "sessions" and args.sessions_command == "delete":
            return _sessions_delete(args)
        view = _view(args)  # the print-and-exit-0 commands (jobs, sessions, export)
    except (
        IdentifierError,
        SettingsUnreadableError,
        CredentialsUnreadableError,
        SpecLoadError,
    ) as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    if view is None:
        parser.print_help()
    else:
        print(view)
    return 0


def _announce_init(outcome: InitOutcome) -> None:
    """Narrate the init pass to stderr (stdout stays clean for view/--json output).

    Args:
        outcome: What the init interview decided.
    """
    # set_active ran at startup off $LANG (config had no language yet). Now that init has
    # chosen one, re-seed the global active so this narration -- and every user string after
    # init in this process -- speaks the chosen language, not the OS locale.
    i18n.set_active(i18n.load_localizer(outcome.language))
    loc = i18n.active()
    if outcome.fresh:
        print(
            loc.t(
                "init.announce.fresh",
                language=outcome.language,
                name=outcome.name,
                role=outcome.role.label,
                role_slug=outcome.role.slug,
                environment=outcome.environment.label,
                environment_slug=outcome.environment.slug,
            ),
            file=sys.stderr,
        )
    else:  # legacy install: the answers were merged into the existing config
        print(loc.t("init.announce.legacy"), file=sys.stderr)
        for change in outcome.overwrites:  # surface each replaced value, never silently
            print(loc.t("init.announce.updated", change=change), file=sys.stderr)
    if outcome.client is not None:
        print(loc.t("init.announce.client", client=outcome.client), file=sys.stderr)
    elif not outcome.found:
        print(loc.t("init.announce.no_client"), file=sys.stderr)
    if outcome.persona is not None:
        print(loc.t("init.announce.persona", persona=outcome.persona), file=sys.stderr)


def _announce_migration(report: MigrationReport) -> None:
    """Narrate a layout migration to stderr, only when it actually moved or skipped.

    Args:
        report: What the migration relocated into the environment (and left behind).
    """
    if not report.did_anything:
        return
    loc = i18n.active()
    if report.moved:
        print(
            loc.t(
                "migration.moved",
                count=len(report.moved),
                environment=report.environment,
                items=", ".join(report.moved),
            ),
            file=sys.stderr,
        )
    if report.skipped:  # a same-named entry already existed at the target — never overwritten
        print(
            loc.t(
                "migration.skipped",
                count=len(report.skipped),
                environment=report.environment,
                items=", ".join(report.skipped),
            ),
            file=sys.stderr,
        )


def _announce_slug_migration(report: SlugMigrationReport) -> None:
    """Narrate the slug migration to stderr, only when it renamed something.

    Args:
        report: The role/environment folders renamed from raw names to clean slugs.
    """
    if not report.did_anything:
        return
    loc = i18n.active()
    items = ", ".join(f"{old} → {new}" for old, new in report.renamed)
    print(loc.t("migration.slugs", count=len(report.renamed), items=items), file=sys.stderr)


def _announce_legacy_migration(report: LegacyMigrationReport) -> None:
    """Narrate the one-time legacy import into attachments, when it did anything.

    Args:
        report: What was imported, left out and rewritten.
    """
    if not report.did_anything:
        return
    loc = i18n.active()
    if report.imported:
        items = ", ".join(report.imported)
        print(
            loc.t("migration.legacy.imported", count=len(report.imported), items=items),
            file=sys.stderr,
        )
    for name, reason in report.skipped:
        print(loc.t("migration.legacy.skipped", name=name, reason=loc.t(reason)), file=sys.stderr)
    if report.config_rewritten:
        print(loc.t("migration.legacy.config"), file=sys.stderr)
    if report.folder:
        print(loc.t("migration.legacy.folder", folder=report.folder), file=sys.stderr)


def _run_init() -> int:
    """Run the setup interview, then the layout/slug migrations — the ``gmlw init`` flow.

    Shared by the ``init`` command, the first-run funnel, and the TUI's Config → Setup verb.
    Re-running on an initialised install merges the answers into the existing config (never
    wipes). Returns ``0``.
    """
    _announce_init(build_init().execute())
    _announce_migration(build_migrate_layout().execute())
    _announce_slug_migration(build_migrate_slugs().execute())
    _announce_legacy_migration(build_migrate_legacy_workflows().execute())
    print(i18n.t("init.reinit_hint"), file=sys.stderr)  # how to re-run setup from the menu
    return 0


def _index() -> int:
    """Bare ``gmlw``: run the forced setup on a fresh install, else open the interactive menu.

    First run wins over everything — a brand-new user is funnelled through init before any
    menu. Once initialised, bare ``gmlw`` becomes the front door: on a terminal it opens the
    ``gmlw tui`` menu; off a terminal ``_tui`` falls back to the plain capability index, so a
    piped/scripted ``gmlw`` never blocks on a menu.
    """
    if config.init_version() is None:  # first run — setup must win over the menu
        return _run_init()
    return _tui()


def _capability_index() -> int:
    """Print the grouped capability index — the non-TTY fallback for bare ``gmlw``/``tui``."""
    print(render_index(i18n.active()))
    return 0


def _help(args: argparse.Namespace) -> int:
    """``gmlw help`` lists the topics; ``gmlw help <topic>`` explains one."""
    loc = i18n.active()
    if args.topic is None:
        print(render_topic_list(loc))
        return 0
    body = render_topic(loc, args.topic)
    if body is None:
        print(i18n.t("help.unknown", topic=args.topic), file=sys.stderr)
        return 2
    print(body)
    return 0


def _view(args: argparse.Namespace) -> str | None:
    """Render a read-only command's output, or ``None`` if it isn't one."""
    as_json = bool(getattr(args, "json", False))
    if args.command == "jobs":
        tag = None if args.tag is None else str(args.tag)
        summaries = build_list_jobs().execute(tag)
        return (
            _as_json([asdict(s) for s in summaries]) if as_json else format_jobs(summaries, tag=tag)
        )
    if args.command == "sessions":
        job = JobId(args.job)
        sessions = build_list_sessions().execute(job)
        if as_json:
            return _as_json([asdict(s) for s in sessions])
        return format_sessions(job, sessions)
    if args.command == "export":
        job = JobId(args.job)
        report = build_export_usage().execute(job)
        return _as_json(asdict(report)) if as_json else format_usage(report)
    if args.command == "clients":
        statuses = build_list_clients().execute()
        return _as_json([asdict(s) for s in statuses]) if as_json else format_clients(statuses)
    return None


def _unique(values: Sequence[str]) -> list[str]:
    """Drop repeats while keeping the order asked for.

    ``gmlw jobs delete a b a`` is one request for two jobs, not a request to delete ``a``
    twice — and the second pass would find nothing and look like a failure.
    """
    return list(dict.fromkeys(values))


def _confirm_delete(preview: str, *, assume_yes: bool) -> bool:
    """Show what a delete would remove and ask whether to go ahead.

    Follows ``_confirm_replace``: the question is only asked where somebody can answer
    it, and off a tty the answer is no. ``--yes`` is what a script uses instead — the
    preview is skipped with it, since nothing would be reading it.

    Args:
        preview: The rendered footprint of what would be removed.
        assume_yes: Whether ``--yes`` already answered the question.

    Returns:
        ``True`` to go ahead.
    """
    if assume_yes:
        return True
    print(preview, file=sys.stderr)
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        print(i18n.t("delete.no_tty"), file=sys.stderr)
        return False
    return input(i18n.t("delete.confirm")).strip().lower() in _AFFIRMATIVE


def _jobs_delete(args: argparse.Namespace) -> int:
    """Delete whole jobs — ``gmlw jobs delete``."""
    return _delete_jobs(_unique([JobId(job) for job in args.job]), assume_yes=bool(args.yes))


def _delete_jobs(jobs: Sequence[str], *, assume_yes: bool) -> int:
    """Preview, confirm, then delete jobs — the `gmlw jobs delete` path.

    Args:
        jobs: The validated job ids to delete.
        assume_yes: Skip the confirmation (``--yes``).

    Returns:
        The process exit code: ``2`` when a job is unknown or the delete was declined,
        matching ``attachment import``'s "nothing happened, and you asked for something";
        ``1`` when some of the jobs could not be removed.
    """
    if not jobs:
        return 0
    delete = build_delete_jobs()
    try:
        footprints = delete.preview(jobs)
    except NoSuchJobError as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    if not _confirm_delete(format_job_footprints(footprints), assume_yes=assume_yes):
        print(i18n.t("delete.cancelled"), file=sys.stderr)
        return 2
    outcome = delete.execute(jobs)
    kept = [footprint for footprint in outcome if not footprint.removed]
    if not kept:
        print(i18n.t("delete.jobs.done", count=len(outcome)), file=sys.stderr)
        return 0
    # The receipt: only what stayed, in the rows the user already read before confirming.
    print(format_job_footprints(kept, heading=False), file=sys.stderr)
    print(_jobs_partial(len(outcome), len(kept)), file=sys.stderr)
    return 1


def _jobs_partial(count: int, kept: int) -> str:
    """The summary of a job delete that removed some of what it was asked to, not all."""
    return i18n.t("delete.jobs.partial", removed=count - kept, count=count, kept=kept)


def _health(args: argparse.Namespace) -> int:
    """Show the connection incidents of recent sessions — ``gmlw health``."""
    job = None if args.job is None else JobId(args.job)
    report = build_report_health().execute(days=int(args.days), job=job)
    print(_as_json(asdict(report)) if bool(args.json) else format_health(report))
    return 0


def format_health(
    report: HealthReport, loc: i18n.Localizer | None = None, *, latest: int = 20
) -> str:
    """Render the connection health: one line per day, then the latest incidents.

    Args:
        report: The health report to render.
        loc: The localiser to render through; defaults to the active language.
        latest: How many of the most recent incidents to list.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    scope = report.job if report.job is not None else loc.t("health.all_jobs")
    lines = [loc.t("health.header", days=report.days, scope=scope), ""]
    if not report.incidents:
        lines.append(loc.t("health.none"))
        return "\n".join(lines)
    lines += [
        loc.t(
            "health.day_row",
            day=day.day,
            lost=day.connection_lost,
            cut=day.stream_interrupted,
        )
        for day in report.by_day
    ]
    lines += ["", loc.t("health.latest", count=min(latest, len(report.incidents)))]
    lines += [format_incident(incident, loc) for incident in report.incidents[:latest]]
    return "\n".join(lines)


def format_incident(incident: Incident, loc: i18n.Localizer | None = None) -> str:
    """One incident on one line: when, which session, what kind, and the cause."""
    loc = loc or i18n.active()
    return loc.t(
        "health.incident_row",
        when=_when(incident.occurred_at),
        job=incident.job,
        session=incident.session_id,
        kind=loc.t(f"health.kind.{incident.kind.value}"),
        cause=incident.cause,
    )


def _when(timestamp: float) -> str:
    """Render an epoch timestamp as a local ``YYYY-MM-DD HH:MM:SS``."""
    return datetime.fromtimestamp(timestamp).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _jobs_tag(args: argparse.Namespace) -> int:
    """Put tags on a job, or take them off — ``gmlw jobs tag|untag <job> <tag>...``."""
    job = JobId(args.job)
    tagger = build_tag_jobs()
    try:
        if args.jobs_command == "tag":
            tags = tagger.add(job, list(args.tags))
        else:
            tags = tagger.remove(job, list(args.tags))
    except NoSuchJobError as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    if tags:
        print(i18n.t("jobs.tags.now", job=job, tags=format_tags(tags)))
    else:
        print(i18n.t("jobs.tags.none", job=job))
    return 0


def _sessions_delete(args: argparse.Namespace) -> int:
    """Delete sessions from one job — ``gmlw sessions <job> delete``."""
    return _delete_sessions(JobId(args.job), _unique(list(args.session)), assume_yes=bool(args.yes))


def _delete_sessions(job: str, sessions: Sequence[str], *, assume_yes: bool) -> int:
    """Preview, confirm, then delete sessions — the `gmlw sessions <job> delete` path.

    Args:
        job: The job the sessions belong to.
        sessions: The session ids to delete.
        assume_yes: Skip the confirmation (``--yes``).

    Returns:
        The process exit code (``2`` when an id is unknown or the delete was declined,
        ``1`` when some of the sessions could not be removed).
    """
    if not sessions:
        return 0
    delete = build_delete_sessions()
    try:
        footprints = delete.preview(job, sessions)
    except (NoSuchJobError, NoSuchSessionError) as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    if not _confirm_delete(format_session_footprints(job, footprints), assume_yes=assume_yes):
        print(i18n.t("delete.cancelled"), file=sys.stderr)
        return 2
    outcome = delete.execute(job, sessions)
    kept = [footprint for footprint in outcome if not footprint.removed]
    if not kept:
        print(i18n.t("delete.sessions.done", count=len(outcome), job=job), file=sys.stderr)
        return 0
    print(format_session_footprints(job, kept, heading=False), file=sys.stderr)
    print(_sessions_partial(job, len(outcome), len(kept)), file=sys.stderr)
    return 1


def _sessions_partial(job: str, count: int, kept: int) -> str:
    """The summary of a session delete that removed some of what it was asked to, not all."""
    return i18n.t("delete.sessions.partial", removed=count - kept, count=count, kept=kept, job=job)


def _client(raw: str | None) -> str:
    """Resolve the client to wrap: the explicit ``--client``, else the config default."""
    return raw if raw else config.default_client()


def format_client_guidance(readiness: ClientReadiness, loc: i18n.Localizer | None = None) -> str:
    """Render install/login guidance for a client that cannot launch.

    Args:
        readiness: The not-ready verdict from the client check.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The guidance text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    system = platform.system()
    if readiness.missing is not None:
        info = readiness.missing
        lines = [
            loc.t("client.guidance.missing", client=repr(readiness.client), display=info.display),
            loc.t("client.guidance.install", command=info.install_for(system)),
            loc.t("client.guidance.login", login=info.login_for(loc)),
        ]
        others = [name for name in readiness.installed if name != readiness.client]
        if others:
            lines.append(loc.t("client.guidance.use_other", other=others[0]))
    else:
        supported = ", ".join(info.name for info in client_catalog.SUPPORTED)
        lines = [
            loc.t(
                "client.guidance.unsupported",
                client=repr(readiness.client),
                supported=supported,
            )
        ]
    if not readiness.installed:
        lines += ["", loc.t("client.guidance.none_installed")]
        width = max(len(info.name) for info in client_catalog.SUPPORTED)
        for info in client_catalog.SUPPORTED:
            lines.append(f"  {info.name:<{width}}  {info.install_for(system)}")
        lines.append(loc.t("client.guidance.then_login"))
    return "\n".join(lines)


def _preflight_client(client: str) -> bool:
    """Print guidance and return ``False`` when the resolved client cannot launch."""
    readiness = build_check_client_ready().execute(client)
    if readiness.ready:
        return True
    print(format_client_guidance(readiness), file=sys.stderr)
    return False


def _preflight_cwd() -> bool:
    """Return ``False`` (with guidance) when the working directory no longer exists.

    A client launched from a deleted directory dies with a cryptic ``getcwd``/``uv_cwd``
    error; catch it here and say so plainly instead.
    """
    try:
        os.getcwd()  # noqa: PTH109  (a probe for a live cwd; Path.cwd() would be equivalent)
    except OSError:
        print(i18n.t("preflight.cwd_gone"), file=sys.stderr)
        return False
    return True


def _preflight_resume_cwd(cwd: str | None) -> bool:
    """Return ``False`` (with guidance) when a resumed session's folder no longer exists.

    A specific session resumes in the folder it was launched in (Claude's resume is scoped
    to it); if that folder was since deleted, the client would die on ``subprocess.run(
    cwd=...)`` with a cryptic error. Name the missing folder plainly instead. ``None`` (a
    pre-folder session) resumes in the current directory, which ``_preflight_cwd`` covers.
    """
    if cwd is None:
        return True
    if not Path(cwd).is_dir():
        print(i18n.t("preflight.resume_cwd_gone", cwd=cwd), file=sys.stderr)
        return False
    return True


_MAX_STATUSLINE_BYTES = 1_000_000  # a client's status payload is small JSON; cap the read


def _statusline() -> int:
    # A status line must always degrade to a printable line, never raise: the client
    # renders this output in place of its own status, so a traceback would land on screen.
    try:
        payload = "" if sys.stdin.isatty() else sys.stdin.read(_MAX_STATUSLINE_BYTES)
        # The launching caller exports GMLW_CLIENT so the status line parses with the
        # right client's parser (claude's quota vs cursor's plan block).
        client = os.environ.get("GMLW_CLIENT")
        payload = _with_cursor_plan(payload, client)
        line = build_render_statusline(client).execute(
            payload,
            os.environ.get("GMLW_JOB"),
            os.environ.get("GMLW_SESSION"),
        )
    except Exception as error:  # noqa: BLE001  degrade to an empty line, never error at the client
        log.warning(i18n.t("log.status_render_failed", error=error))
        print()
        return 0
    print(line)
    return 0


def _with_cursor_plan(payload_json: str, client: str | None) -> str:  # noqa: PLR0911  (guards)
    """Merge the cached cursor allowance (``~/.gmlw/cursor-plan.json``) into the payload.

    Cursor does not pipe its plan pools to the status line, so an external fetcher caches
    them; when the payload lacks a ``plan`` and a cache exists, fold it in for the parser.

    Args:
        payload_json: The raw status payload from the client.
        client: The launching client (``GMLW_CLIENT``); only ``cursor`` has a plan block.

    Returns:
        The payload JSON, with a ``plan`` merged in when applicable, else unchanged.
    """
    if client != "cursor":
        return payload_json
    try:
        loaded: object = json.loads(payload_json) if payload_json.strip() else {}
    except json.JSONDecodeError:
        return payload_json
    if not isinstance(loaded, dict):
        return payload_json
    payload = cast("dict[str, object]", loaded)
    if payload.get("plan"):  # cursor already carried a plan
        return payload_json
    try:
        plan = json.loads(paths.CURSOR_PLAN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return payload_json
    if not isinstance(plan, dict):
        return payload_json
    payload["plan"] = cast("dict[str, object]", plan)
    return json.dumps(payload)


class _Terminated(Exception):  # noqa: N818  (a control-flow signal, not an *Error)
    """Raised by the SIGTERM/SIGHUP handler to unwind session teardown before exit."""


def _ignore_sigint(_signum: int, _frame: object) -> None:
    """Swallow Ctrl+C while the client owns the terminal.

    The interactive client handles its own interrupt; gmlw only supervises, so it must
    not die on SIGINT or let a second Ctrl+C abort teardown. Custom handlers reset to the
    default in the child on exec, so the client still receives Ctrl+C normally.
    """


def _on_termination(signum: int, _frame: object) -> None:
    """Convert a kill/hangup into a clean unwind so session teardown runs before exit.

    Raising here propagates out of the blocked client run and triggers the ``finally``
    that stops the relay and restores the client's status-line hook -- so a killed or
    hung-up session never leaves gmlw's hook behind in the user's settings. The handler
    resets itself first, so a repeat signal terminates immediately and cleanup can't
    itself wedge the exit.
    """
    signal.signal(signum, signal.SIG_DFL)
    raise _Terminated


# SIGTERM everywhere; SIGHUP (terminal hangup) only where the platform has it (not Windows).
_TERMINATION_SIGNALS = (
    (signal.SIGTERM, signal.SIGHUP) if hasattr(signal, "SIGHUP") else (signal.SIGTERM,)
)


@contextlib.contextmanager
def _client_owns_interrupts() -> Generator[None, None, None]:
    """Make the client own interrupts for the duration of a session.

    gmlw ignores Ctrl+C (the client handles it) and turns a kill/hangup into a clean
    unwind so teardown runs, then restores every prior handler on the way out.
    """
    previous = [(signal.SIGINT, signal.signal(signal.SIGINT, _ignore_sigint))]
    previous += [(sig, signal.signal(sig, _on_termination)) for sig in _TERMINATION_SIGNALS]
    try:
        yield
    finally:
        for sig, handler in previous:
            signal.signal(sig, handler)


def _farewell() -> str | None:
    """Return a parting line when a companion persona is set, else ``None``.

    Mirrors the host greeting's gating and name, printed on the return once the client
    has exited -- the first, visible seed of the session's exit summary.

    Returns:
        ``"Bye, <name>."``, or ``None`` when the companion is off.
    """
    settings = config.companion()
    if settings.persona is None:
        return None
    return i18n.t("farewell", name=settings.name or getpass.getuser())


def _tui() -> int:
    """Run the interactive menu until something ends the session.

    Two kinds of thing come back out of the menu, and the difference is this loop. A
    *launch* (start, resume, run, authoring) gives the terminal to a client and gmlw is
    done when that client is. Everything else -- exporting, importing, deleting, re-running
    setup -- is an errand: it needs the restored terminal to ask a question or print a
    result, and then the user is still in the middle of using the menu. Those return here
    and the menu is rebuilt, which is also what refreshes the job list a delete just changed.

    Off a TTY we never build the app -- we fall back to the plain capability index,
    honouring the "non-TTY never blocks on a menu" contract.

    Returns:
        The process exit code.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return _capability_index()  # never the menu off a TTY; never recurse back into _index
    while True:
        choice = _run_menu()
        if choice is None:  # quit from the menu itself
            return 0
        exit_code = _act_on_tui_choice(choice)
        if exit_code is not None:  # a launch: the session is over, so gmlw is too
            return exit_code
        _pause_before_menu()


def _pause_before_menu() -> None:
    """Hold the errand's result on screen until the user is ready to go back.

    Without this the menu repaints over the answer immediately: an errand prints to the
    restored terminal, and the next full-screen repaint takes that line with it. The
    outcome of a *delete* is the last thing that should flash past unread.
    """
    print(i18n.t("tui.return"), file=sys.stderr)
    with contextlib.suppress(EOFError, KeyboardInterrupt):
        input()


def _run_menu() -> MenuChoice | None:  # noqa: PLR0915  (menu + preflights, one per browser's data)
    """Build the menu on the current state and run it once.

    Rebuilt per pass rather than kept alive: every browser's data is a snapshot taken here,
    so re-entering after an errand is what makes a deleted job leave the list, a new
    attachment appear, and a changed setting show its new value.

    Returns:
        What the user asked for, or ``None`` if they quit.
    """
    from generic_ml_wrapper.adapter.inbound.tui.menu_app import (  # noqa: PLC0415  lazy: tui adapter
        ClientChoice,
        ClientRow,
        ConfigCatalog,
        ConfigSetResult,
        ConfigSetting,
        CreateOutcome,
        Deleter,
        HealthDayView,
        JobChoice,
        MenuApp,
        SessionChoice,
        SwitchChoice,
        Switcher,
        UsageView,
    )

    def _job_choices() -> list[JobChoice]:
        return [
            JobChoice(job=s.job, session_count=s.session_count, tags=s.tags)
            for s in build_list_jobs().execute()
        ]

    def _retag_job(job: str, line: str) -> str | None:  # the menu's tag editor: words in, kept
        try:
            build_tag_jobs().replace(job, line.split())
        except (IdentifierError, NoSuchJobError) as error:
            return _render_error(error)
        return None

    def _preview_jobs(selected: tuple[str, ...]) -> str:
        try:
            return format_job_footprints(build_delete_jobs().preview(list(selected)))
        except NoSuchJobError as error:  # the list went stale under us
            return _render_error(error)

    def _delete_jobs_in_app(selected: tuple[str, ...]) -> str:
        try:
            outcome = build_delete_jobs().execute(list(selected))
        except NoSuchJobError as error:
            return _render_error(error)
        kept = sum(1 for footprint in outcome if not footprint.removed)
        if not kept:
            return i18n.t("delete.jobs.done", count=len(outcome))
        return _jobs_partial(len(outcome), kept)

    def _preview_sessions(job: str, selected: tuple[str, ...]) -> str:
        try:
            return format_session_footprints(
                job, build_delete_sessions().preview(job, list(selected))
            )
        except (NoSuchJobError, NoSuchSessionError) as error:
            return _render_error(error)

    def _delete_sessions_in_app(job: str, selected: tuple[str, ...]) -> str:
        try:
            outcome = build_delete_sessions().execute(job, list(selected))
        except (NoSuchJobError, NoSuchSessionError) as error:
            return _render_error(error)
        kept = sum(1 for footprint in outcome if not footprint.removed)
        if not kept:
            return i18n.t("delete.sessions.done", count=len(outcome), job=job)
        return _sessions_partial(job, len(outcome), kept)

    # Deleting is the one write the menu does without leaving: it asks in-app and calls
    # these, so the user stays on the list they are clearing instead of being returned to
    # the front door. The app still holds no port -- these closures do.
    deleter = Deleter(
        preview_jobs=_preview_jobs,
        delete_jobs=_delete_jobs_in_app,
        preview_sessions=_preview_sessions,
        delete_sessions=_delete_sessions_in_app,
    )

    shelf = _shelf()

    def _launch_clients() -> list[ClientChoice]:
        # Re-read per open, not snapshotted with the rest: a default just changed in Config
        # has to be the one marked here, and this read is a PATH lookup plus a config read,
        # not a version probe.
        return [
            ClientChoice(name=c.name, display=c.display, is_default=c.is_default, custom=c.custom)
            for c in build_list_launch_clients().execute()
        ]

    def _sessions_for(job: str) -> list[SessionChoice]:
        summaries = build_list_sessions().execute(job)  # oldest-first; the last is the latest
        return [
            SessionChoice(
                session_id=s.session_id,
                client=s.client,
                cwd=s.cwd,
                resumable=s.resumable,
                date=(s.created_at or "")[:16],  # "YYYY-MM-DD HH:MM"
                is_latest=(i == len(summaries) - 1),
                usage=format_session_usage(s),  # rendered here: the app holds no formatter
                attachment=s.attachment,
            )
            for i, s in enumerate(summaries)
        ]

    def _usage_view(job: str) -> UsageView:  # runs on a worker thread: fresh store/connection
        report = build_export_usage().execute(JobId(job))
        loc = i18n.active()
        if report.turn_count == 0 and not report.session_costs:
            return UsageView(
                job=job,
                empty=True,
                summary=loc.t("usage.none", job=repr(job)),
                model_rows=(),
                session_rows=(),
            )
        summary = loc.t(
            "usage.total",
            count=report.turn_count,
            tokens=_tokens(report.input_tokens, report.output_tokens, report.cache_tokens, loc),
            duration=f"{report.duration_s:.1f}",
            total=f"{report.total_usd:.2f}",
        )
        model_rows = tuple(
            (
                model.model,
                str(model.calls),
                str(model.input_tokens),
                str(model.output_tokens),
                str(model.cache_tokens),
                f"{model.duration_s:.1f}",
            )
            for model in report.models
        )
        session_rows = tuple(
            (cost.session_id, f"{cost.cost_usd:.2f}") for cost in report.session_costs
        )
        return UsageView(
            job=job, empty=False, summary=summary, model_rows=model_rows, session_rows=session_rows
        )

    def _health_days() -> list[HealthDayView]:  # the Health screen: the last two weeks
        report = build_report_health().execute(days=14)
        per_day: dict[str, list[Incident]] = {}
        for incident in report.incidents:
            day = datetime.fromtimestamp(incident.occurred_at).astimezone().date().isoformat()
            per_day.setdefault(day, []).append(incident)
        return [
            HealthDayView(
                day=day.day,
                summary=loc.t(
                    "health.day_summary", lost=day.connection_lost, cut=day.stream_interrupted
                ),
                count=day.connection_lost + day.stream_interrupted,
                rows=tuple(
                    (
                        _clock(incident.occurred_at),
                        incident.job,
                        incident.session_id,
                        loc.t(f"health.kind.{incident.kind.value}"),
                        incident.cause,
                    )
                    for incident in per_day.get(day.day, [])
                ),
            )
            for day in report.by_day
        ]

    def _save_usage(job: str) -> str:  # writes the full JSON report; returns the file path
        return str(build_save_usage_report().execute(JobId(job)))

    def _clients() -> list[ClientRow]:  # runs on a worker thread: version reads are subprocesses
        return [
            ClientRow(
                client=status.display,
                version=_client_version_label(status, loc),
                resumable=loc.t("clients.yes") if status.resumable else loc.t("clients.no"),
                default=loc.t("clients.default_marker") if status.is_default else "",
                name=status.name,  # not shown: the id written when the row is made the default
                note=(  # the caveat on the resume cell, kept out of the column
                    f"{loc.t('clients.col.resumable')}: {loc.t(status.resume_hint)}"
                    if status.resume_hint
                    else ""
                ),
            )
            for status in build_list_clients().execute()
        ]

    # The config switchers (browsers that mutate config in place, no hand-off): each fetches
    # its options + current value and injects an ``apply`` setter and, for the folder-backed
    # axes, a ``create``. The app stays pure -- the wiring owns every outbound call.
    config_commands = build_config_commands()
    catalog = build_axis_catalog()

    t = i18n.active().t

    def _switcher(
        label_key: str, key: str, choices: list[SwitchChoice], kind: AxisKind | None = None
    ) -> Switcher:
        current = config_commands.get(key).value
        crumb = f"gmlw > {t('tui.config')} > {t(label_key)}"

        def apply(value: str) -> str:  # localised confirmation, shown in the detail panel
            changed = config_commands.set(key, value).changed
            return t("tui.switch.set" if changed else "tui.switch.unchanged", value=value)

        def create(label: str) -> CreateOutcome:
            try:  # create + make it the default, so "New" from the switcher also switches
                result = build_create_axis().execute(
                    CreateAxisCommand(kind=cast(AxisKind, kind), label=label, make_default=True)
                )
            except AxisLabelError:
                return CreateOutcome(None, t("tui.create.bad"))
            except AxisExistsError:
                return CreateOutcome(None, t("tui.create.exists"))
            return CreateOutcome(SwitchChoice(result.slug, result.label, ""), "")

        return Switcher(
            key=key,
            crumb=crumb,
            choices=choices,
            current=current if isinstance(current, str) else None,
            apply=apply,
            create=None if kind is None else create,
        )

    personas = [
        SwitchChoice(p.name, p.name, p.description) for p in build_list_personas().execute()
    ]
    environments = [
        SwitchChoice(e.slug, e.label, e.description) for e in catalog.list(AxisKind.ENVIRONMENT)
    ]
    roles = [SwitchChoice(e.slug, e.label, e.description) for e in catalog.list(AxisKind.ROLE)]

    switchers: dict[str, Switcher] = {}
    if personas:
        switchers["persona"] = _switcher("tui.cfg.persona", "companion.persona", personas)
    switchers["environment"] = _switcher(
        "tui.cfg.environment", "profile.default_environment", environments, AxisKind.ENVIRONMENT
    )
    switchers["role"] = _switcher("tui.cfg.role", "profile.default_role", roles, AxisKind.ROLE)

    # Config Get/Set: the settings snapshot + a setter, injected like the switchers. The picker
    # reads the snapshot; a set goes through the same ConfigCommands.set the CLI's `config set`
    # uses (values/defaults pre-rendered through _setting_value so the app stays format-free).
    loc = i18n.active()

    # A setting with a screen of its own is changed there, and only there. Offering it again
    # under Get/Set/List gave two readers of one value, each a snapshot taken before the
    # app starts, which disagreed the moment either wrote. Derived from the menus rather
    # than listed beside them, so adding a switcher drops its key here on its own.
    dedicated_menu_keys = {switcher.key for switcher in switchers.values()} | {CLIENT_DEFAULT_KEY}

    def _config_settings() -> list[ConfigSetting]:
        return [
            ConfigSetting(
                key=view.key,
                value=_setting_value(view.value, loc),
                default=_setting_value(view.default, loc),
                type_name=view.type_name,
                choices=view.choices,
                description=view.description,
            )
            for view in config_commands.list()
            if view.key not in dedicated_menu_keys
        ]

    def _apply_setting(key: str, raw: str) -> ConfigSetResult:
        try:  # a value out of range keeps the editor open with the localised reason
            outcome = config_commands.set(key, raw)
        except settings_registry.InvalidSettingValueError as error:
            return ConfigSetResult(ok=False, message=_render_error(error))
        return ConfigSetResult(
            ok=True, message=_format_set_outcome(outcome), value=_setting_value(outcome.new, loc)
        )

    def _set_default_client(name: str) -> ConfigSetResult:  # Config → Clients: pick the default
        return _apply_setting(CLIENT_DEFAULT_KEY, name)

    config_catalog = ConfigCatalog(
        crumb=f"gmlw > {t('tui.config')}",
        settings=_config_settings(),
        apply=_apply_setting,
    )

    def _validate_job(name: str) -> str | None:  # in-form validation before any teardown
        try:
            JobId(name)
        except IdentifierError:
            return t("tui.newjob.invalid")
        return None

    # The menu opens on a *snapshot* of the default client, for the rows that mention it.
    # The launch re-reads it, because the user may have changed it in Config while the menu
    # was up -- resolving it once, here, would launch the client they just left.
    return MenuApp(
        _job_choices(),
        switchers=switchers,
        validate_job=_validate_job,
        sessions_for=_sessions_for,
        usage_view=_usage_view,
        health=_health_days,
        save_usage=_save_usage,
        rules=build_list_rules().execute,
        clients=_clients,
        set_default_client=_set_default_client,
        config=config_catalog,
        current_client=_client(None),
        deleter=deleter,
        reload_jobs=_job_choices,
        retag_job=_retag_job,
        shelf=shelf,
        launch_clients=_launch_clients,
    ).run()  # blocks; terminal restored on return


def _act_on_tui_choice(choice: MenuChoice) -> int | None:
    """Carry out what the menu was asked for, on the restored terminal.

    Everything here runs *after* ``run()`` returned, which is the point: the app hands
    back an intention and this does it, so the risky parts -- launching a client, asking a
    question that needs a tty -- happen outside the event loop rather than inside it.

    Args:
        choice: What the user asked the menu to do.

    Returns:
        The process exit code, or ``None`` for an errand -- one that borrowed the terminal
        to ask or report something and leaves the user still working in the menu. An
        errand's own exit code is deliberately dropped: a declined delete or a refused
        import is not a reason to end the session, it is a reason to go back.
    """
    # The client the launch was pointed at, else the configured default read *after* the
    # menu: a default-client switch made in Config (or in the Clients view) must apply to
    # this launch, not only to the next run of gmlw. Ignored on resume -- a resumed session
    # carries its own client.
    client = choice.client or _client(None)
    # -- the one errand: done on the terminal, then back to the menu -------------------- #
    if choice.action == "init":
        # Config → Setup genuinely needs the terminal: it is an interview, and it can
        # install a client. Everything else the menu does that writes -- deleting,
        # exporting, importing -- stays in the app, so the user keeps their place.
        _run_init()
        return None
    # -- launches: the terminal goes to a client, and gmlw ends with it ----------------- #
    if choice.job is None or choice.action not in ("start", "resume"):
        return 0
    resume = choice.action == "resume"
    picked_cwd: str | None = None
    if resume and choice.session is not None:  # a specific session relaunches in its own folder
        recorded = build_list_sessions().execute(choice.job)
        picked = next((s for s in recorded if s.session_id == choice.session), None)
        picked_cwd = picked.cwd if picked is not None else None
    return _tui_launch_job(
        choice.job,
        resume,
        choice.session,
        picked_cwd,
        client,
        attachment=choice.attachment,
        attachment_version=choice.attachment_version,
        note=choice.note,
    )


def _tui_launch_job(  # noqa: PLR0913  (the TUI choice, unpacked; what it attaches keyword-only)
    job: str,
    resume: bool,
    session: str | None,
    picked_cwd: str | None,
    client: str,
    *,
    attachment: str | None = None,
    attachment_version: str | None = None,
    note: str | None = None,
) -> int:
    """Launch (or resume) a job from the TUI's choice — the hand-off after ``run()`` returns.

    Args:
        job: The job to launch.
        resume: Whether this reopens an existing session.
        session: The specific session id to resume, or ``None`` for the latest / a new one.
        picked_cwd: A resumed session's stored folder to relaunch in, or ``None``.
        client: The resolved client to wrap.
        attachment: The attachment to start a new session with, or ``None``.
        attachment_version: That attachment's version, or ``None`` for the highest.
        note: An extra paragraph for the new session's opening message, or ``None``.

    Returns:
        The process exit code.
    """
    command = StartJobCommand(
        job=JobId(job),
        client=client,
        resume_latest=resume and session is None,  # a picked session wins over "latest"
        resume_session=session,
        attachment=attachment,
        attachment_version=attachment_version,
        note=note,
    )
    # Guard the folder the launch will actually use: a resumed session's stored folder, or
    # the current directory for a new start (or a pre-folder resume, whose cwd is ``None``).
    if picked_cwd is not None:
        if not _preflight_resume_cwd(picked_cwd):
            return 2
    elif not _preflight_cwd():
        return 2
    if not resume and not _preflight_client(client):  # a new session needs the client installed
        return 2
    with _client_owns_interrupts():
        try:
            result = build_start_job().execute(command)
        except _Terminated:
            return 143
        except (
            ResumeNotSupportedError,
            AttachmentError,
            AttachmentVersionError,
        ) as error:
            print(_render_error(error), file=sys.stderr)
            return 2
    _print_exit_receipt(result)
    return result.exit_code


def _start(args: argparse.Namespace) -> int:
    if args.job is None:  # `gmlw start` with no job — guide instead of an argparse dump
        print(i18n.t("start.needs_job"), file=sys.stderr)
        return 2
    attachment, attachment_version = _attach_target(getattr(args, "attach", None))
    client = _client(args.client)
    command = StartJobCommand(
        job=JobId(args.job),
        client=client,
        resume_latest=bool(args.resume_latest),
        attachment=attachment,
        attachment_version=attachment_version,
        client_args=args.client_args,
        tags=tuple(getattr(args, "tag", None) or ()),
    )
    if not _preflight_cwd():  # deleted working directory — the client would crash on getcwd
        return 2
    if not _preflight_client(client):  # client not installed — guide, don't launch
        return 2
    # The free host greeting (when a companion persona is set) is now injected into the
    # session's context by StartJob, so the client renders it in-band — the launch-time
    # stderr greeting was structurally invisible once the client cleared the screen.
    # The client owns the terminal for the session: it handles Ctrl+C itself, and a
    # kill/hangup is turned into a clean unwind so teardown (relay stop + status-line
    # restore) always runs -- gmlw never leaves its hook behind in the user's settings.
    with _client_owns_interrupts():
        try:
            result = build_start_job().execute(command)
        except _Terminated:
            return 143  # 128 + SIGTERM: terminated, but teardown ran
        except (
            ResumeNotSupportedError,
            AttachmentError,
            AttachmentVersionError,
        ) as error:
            print(_render_error(error))
            return 2
    farewell = _farewell()
    if farewell:
        print(farewell, file=sys.stderr)
    _print_exit_receipt(result)  # the persistent return summary: cost, commands, one tip
    return result.exit_code


def _attach_target(value: str | None) -> tuple[str | None, str | None]:
    """Split ``--attach NAME[@VERSION]`` into the name and the version (``None``: highest)."""
    if value is None:
        return None, None
    name, at, version = str(value).partition("@")
    return name, (version if at else None)


def _print_exit_receipt(result: StartJobResult) -> None:
    """Print the exit receipt to stderr: this session's and the job's cost, then next steps.

    A persistent summary on the return (the client has exited): the cost of the session and
    the job, the resume/report commands, and one usage-driven, suppressible tip. Best-effort
    — the cost line degrades to just the commands if the usage read fails, never raising on
    the way out.
    """
    loc = i18n.active()
    try:
        report = build_export_usage().execute(JobId(result.job))
        session_cost = next(
            (c.cost_usd for c in report.session_costs if c.session_id == result.session_id),
            0.0,
        )
        print(
            loc.t(
                "receipt.cost",
                session=result.session_id,
                session_cost=f"{session_cost:.2f}",
                job=result.job,
                job_cost=f"{report.total_usd:.2f}",
            ),
            file=sys.stderr,
        )
    except Exception as error:  # noqa: BLE001  the receipt must never break a clean exit
        log.debug(i18n.t("log.receipt_failed", error=error))
    print(loc.t("receipt.resume", job=result.job), file=sys.stderr)
    print(loc.t("receipt.report", job=result.job), file=sys.stderr)
    latest = build_check_for_update().execute()
    if latest:
        print(loc.t("receipt.update", latest=latest, current=__version__), file=sys.stderr)
    tip = next_hint(loc)
    if tip:
        print(tip, file=sys.stderr)


def _read_secret() -> str:
    """Read a secret value: a secure prompt at a TTY, else one line from stdin."""
    if sys.stdin.isatty():
        return getpass.getpass("value: ")
    return sys.stdin.readline().rstrip("\n")


def _axis(kind: AxisKind, subcommand: str | None, args: argparse.Namespace) -> int:
    """Create a role/environment from a typed label (``environment new`` / ``role new``).

    Args:
        kind: Which axis this command creates.
        subcommand: The chosen sub-action (only ``new`` today; ``None`` is handled upstream
            by the incomplete-command help).
        args: The parsed arguments (label, description, make_default).

    Returns:
        ``0`` on success, ``2`` on a bad label or an existing slug.
    """
    if subcommand != "new":
        return 0
    try:
        result = build_create_axis().execute(
            CreateAxisCommand(
                kind=kind,
                label=args.label,
                description=args.description,
                make_default=bool(args.make_default),
            )
        )
    except (AxisLabelError, AxisExistsError) as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    print(i18n.t("axis.created", kind=kind.value, label=result.label, slug=result.slug))
    if result.made_default:
        print(i18n.t("axis.made_default", kind=kind.value, slug=result.slug))
    return 0


def _creds(args: argparse.Namespace) -> int:
    if args.creds_command == "set":
        attachment = AttachmentName(args.attachment)
        name = EnvVarName(args.name)
        build_set_credential().execute(
            SetCredentialCommand(attachment=attachment, name=name, value=_read_secret())
        )
        print(i18n.t("creds.stored", attachment=attachment, name=name))
        return 0
    return 0


def _setting_value(value: object, loc: i18n.Localizer) -> str:
    """Render a setting value for display: ``(unset)`` for None, lower-case for bools."""
    if value is None:
        return loc.t("config.unset")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def format_setting_list(views: list[SettingView], loc: i18n.Localizer | None = None) -> str:
    """Render every setting with its current value and description (aligned).

    Args:
        views: The settings to render, in registry order.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    lines = [loc.t("config.list.header", count=len(views)), ""]
    width = max((len(view.key) for view in views), default=0)
    for view in views:
        lines.append(
            loc.t("config.row", key=f"{view.key:<{width}}", value=_setting_value(view.value, loc))
        )
        lines.append(loc.t("config.row_desc", description=view.description))
    return "\n".join(lines)


def format_setting(view: SettingView, loc: i18n.Localizer | None = None) -> str:
    """Render a single setting: value, description, default and any allowed values.

    Args:
        view: The setting to render.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    lines = [
        loc.t("config.get", key=view.key, value=_setting_value(view.value, loc)),
        loc.t("config.get_desc", description=view.description),
        loc.t("config.get_default", default=_setting_value(view.default, loc)),
    ]
    if view.choices is not None:
        lines.append(loc.t("config.get_allowed", choices=", ".join(view.choices)))
    return "\n".join(lines)


def _config(args: argparse.Namespace) -> int:
    commands = build_config_commands()
    as_json = bool(getattr(args, "json", False))
    if args.config_command == "list":
        views = commands.list()
        if as_json:
            print(_as_json([_setting_payload(view) for view in views]))
        else:
            print(format_setting_list(views))
        return 0
    if args.config_command == "get":
        try:
            view = commands.get(args.key)
        except settings_registry.UnknownSettingError:
            print(i18n.t("config.unknown_key", key=args.key), file=sys.stderr)
            return 2
        print(_as_json(_setting_payload(view)) if as_json else format_setting(view))
        return 0
    if args.config_command == "set":
        return _config_set(commands, args.key, args.value)
    return 0


def _config_set(commands: ConfigCommands, key: str, value: str) -> int:
    try:
        outcome = commands.set(key, value)
    except settings_registry.UnknownSettingError:
        print(i18n.t("config.unknown_key", key=key), file=sys.stderr)
        return 2
    except settings_registry.InvalidSettingValueError as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    print(_format_set_outcome(outcome))
    return 0


def _format_set_outcome(outcome: SetOutcome, loc: i18n.Localizer | None = None) -> str:
    """Render the localised summary of a ``config set`` — never silent about the change."""
    loc = loc or i18n.active()
    if not outcome.changed:
        value = _setting_value(outcome.new, loc)
        return loc.t("config.set_unchanged", key=outcome.key, value=value)
    if outcome.new is None:
        return loc.t("config.set_cleared", key=outcome.key, old=_setting_value(outcome.old, loc))
    return loc.t(
        "config.set_changed",
        key=outcome.key,
        new=_setting_value(outcome.new, loc),
        old=_setting_value(outcome.old, loc),
    )


def _setting_payload(view: SettingView) -> dict[str, object]:
    """Render a setting as a JSON-friendly dict."""
    return {
        "key": view.key,
        "value": view.value,
        "default": view.default,
        "type": view.type_name,
        "choices": list(view.choices) if view.choices is not None else None,
        "description": view.description,
    }


def _persona(args: argparse.Namespace) -> int:
    if args.persona_command == "list":
        personas = build_list_personas().execute()
        if bool(args.json):
            payload = [{"name": p.name, "description": p.description} for p in personas]
            print(_as_json(payload))
        else:
            print(format_personas(personas))
        return 0
    return 0


def _attachment(args: argparse.Namespace) -> int:
    """``gmlw attachment``: import, export, list or delete stored attachment versions."""
    command = args.attachment_command
    if command == "import":
        return _attachment_import(str(args.archive))
    if command == "export":
        version = None if args.version is None else str(args.version)
        return _attachment_export(str(args.name), version, Path(str(args.to)))
    if command == "delete":
        return _attachment_delete(str(args.name), str(args.version), assume_yes=bool(args.yes))
    listings = build_list_attachments().execute()
    if bool(args.json):
        payload = [
            {
                "name": item.attachment.name,
                "version": str(item.attachment.version),
                "description": item.attachment.description,
                "main_md_file": item.attachment.main_md_file,
                "intact": item.intact,
            }
            for item in listings
        ]
        print(_as_json(payload))
    else:
        print(format_attachments(listings))
    return 0


def _attachment_import(archive: str) -> int:
    """Import an attachment from a zip — ``gmlw attachment import``."""
    try:
        attachment = build_import_attachment().execute(archive)
    except DomainError as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    print(
        i18n.t("attachment.import.done", name=attachment.name, version=attachment.version),
        file=sys.stderr,
    )
    return 0


def _attachment_export(name: str, version: str | None, folder: Path) -> int:
    """Export a stored version as a zip — ``gmlw attachment export``."""
    try:
        written = build_export_attachment().execute(name, version, folder)
    except DomainError as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    print(i18n.t("attachment.export.written", path=written), file=sys.stderr)
    return 0


def _attachment_delete(name: str, version: str, *, assume_yes: bool) -> int:
    """Confirm, then delete one stored version — ``gmlw attachment delete``.

    The version is looked up before asking, so an unknown one is reported rather than
    confirmed and then refused.
    """
    try:
        stored = [item.attachment for item in build_list_attachments().execute()]
        find(stored, name, AttachmentVersion.parse(version))
    except DomainError as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    preview = i18n.t("delete.attachment.preview", name=name, version=version)
    if not _confirm_delete(preview, assume_yes=assume_yes):
        print(i18n.t("delete.cancelled"), file=sys.stderr)
        return 2
    build_delete_attachment().execute(name, version)
    print(i18n.t("delete.attachment.done", name=name, version=version), file=sys.stderr)
    return 0


def _shelf() -> Shelf:
    """The attachment store's calls for the TUI, each returning the line to show."""
    from generic_ml_wrapper.adapter.inbound.tui.menu_app import (  # noqa: PLC0415  lazy: tui adapter
        AttachmentRow,
        Shelf,
    )

    def _split(key: str) -> tuple[str, str]:
        name, _, version = key.partition("@")
        return name, version

    def _rows() -> list[AttachmentRow]:
        return [
            AttachmentRow(
                item.attachment.name,
                str(item.attachment.version),
                item.attachment.description,
                item.intact,
            )
            for item in build_list_attachments().execute()
        ]

    def _import(archive: str) -> str:
        try:
            attachment = build_import_attachment().execute(archive)
        except DomainError as error:
            return f"✗ {_render_error(error)}"
        return i18n.t("attachment.import.done", name=attachment.name, version=attachment.version)

    def _export(key: str) -> str:
        name, version = _split(key)
        try:
            written = build_export_attachment().execute(name, version, Path.cwd())
        except DomainError as error:
            return f"✗ {_render_error(error)}"
        return i18n.t("attachment.export.written", path=written)

    def _preview(keys: tuple[str, ...]) -> str:
        lines = [i18n.t("delete.attachments.preview", count=len(keys))]
        lines += [f"  {name} {version}" for name, version in map(_split, keys)]
        return "\n".join(lines)

    def _delete(keys: tuple[str, ...]) -> str:
        for name, version in map(_split, keys):
            try:
                build_delete_attachment().execute(name, version)
            except DomainError as error:
                return f"✗ {_render_error(error)}"
        return i18n.t("delete.attachments.done", count=len(keys))

    return Shelf(
        rows=_rows,
        import_zip=_import,
        export=_export,
        preview_delete=_preview,
        delete=_delete,
        modify_note=lambda key: modify_request(*_split(key)),
    )


def _plugins(args: argparse.Namespace) -> int:
    if args.plugins_command == "list":
        plugins = build_list_plugins().execute()
        if bool(args.json):
            payload = [{"id": p.plugin_id, "description": p.description} for p in plugins]
            print(_as_json(payload))
        else:
            print(format_plugins(plugins))
        return 0
    return 0
