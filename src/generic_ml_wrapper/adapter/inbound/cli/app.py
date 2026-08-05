# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The argparse command-line inbound adapter."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
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
from generic_ml_wrapper.application.domain.model.authoring_mode import AuthoringMode
from generic_ml_wrapper.application.domain.model.axis_kind import AxisKind
from generic_ml_wrapper.application.domain.model.client_settings_unusable_error import (
    ClientSettingsUnusableError,
)
from generic_ml_wrapper.application.domain.model.credentials_unusable_error import (
    CredentialsUnusableError,
)
from generic_ml_wrapper.application.domain.model.domain_error import DomainError
from generic_ml_wrapper.application.domain.model.draft import Draft
from generic_ml_wrapper.application.domain.model.env_var_name import EnvVarName
from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.invalid_setting_value_error import (
    InvalidSettingValueError,
)
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.launch_location import (
    LaunchLocation,
    LaunchLocationProblem,
)
from generic_ml_wrapper.application.domain.model.migration_report import MigrationReport
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.domain.model.slug_migration_report import SlugMigrationReport
from generic_ml_wrapper.application.domain.model.unknown_setting_error import UnknownSettingError
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.domain.model.workflow_name import WorkflowName
from generic_ml_wrapper.application.port.inbound.check_client_ready import ClientReadiness
from generic_ml_wrapper.application.port.inbound.config_commands import (
    ConfigCommandsUseCase,
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
from generic_ml_wrapper.application.port.inbound.edit_workflow import (
    EditWorkflowCommand,
    NoEditToResumeError,
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.export_usage import UsageReport
from generic_ml_wrapper.application.port.inbound.import_workflow import (
    ArchiveUnreadableError,
    ImportOutcome,
)
from generic_ml_wrapper.application.port.inbound.init import InitOutcome
from generic_ml_wrapper.application.port.inbound.list_clients import ClientStatus
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary
from generic_ml_wrapper.application.port.inbound.list_sessions import SessionSummary
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflowCommand,
    NewWorkflowResult,
    NoSuchDraftError,
    WorkflowExistsError,
    WorkflowNameError,
    WorkflowOutcome,
)
from generic_ml_wrapper.application.port.inbound.set_credential import SetCredentialCommand
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJobCommand,
    StartJobResult,
    UnknownWorkflowError,
)
from generic_ml_wrapper.application.wiring import localization as i18n
from generic_ml_wrapper.application.wiring.composition import (
    build_application_settings,
    build_axis_catalog,
    build_bootstrap,
    build_check_client_ready,
    build_check_for_update,
    build_check_launch_location,
    build_check_store_contract,
    build_config_commands,
    build_create_axis,
    build_delete_jobs,
    build_delete_sessions,
    build_diagnostics,
    build_edit_workflow,
    build_export_usage,
    build_export_workflow,
    build_guided_chooser,
    build_import_workflow,
    build_init,
    build_list_clients,
    build_list_drafts,
    build_list_jobs,
    build_list_launch_clients,
    build_list_personas,
    build_list_plugins,
    build_list_rules,
    build_list_sessions,
    build_list_supported_clients,
    build_list_workflow_catalog,
    build_list_workflows,
    build_localizer,
    build_migrate_layout,
    build_migrate_slugs,
    build_new_workflow,
    build_render_farewell,
    build_render_statusline,
    build_render_version,
    build_save_usage_report,
    build_set_credential,
    build_start_job,
    build_workflow_chooser,
)
from generic_ml_wrapper.application.wiring.diagnostics_log import log
from generic_ml_wrapper.application.wiring.diagnostics_log import (
    set_active as set_active_diagnostics,
)
from generic_ml_wrapper.application.wiring.spec_loader import SpecLoadError

if TYPE_CHECKING:
    # argparse does not publicly export the type ``add_subparsers`` returns; alias it once
    # (the private reference is confined here) so the parser-builder helpers can type it.
    _SubParsers = argparse._SubParsersAction[argparse.ArgumentParser]  # pyright: ignore[reportPrivateUsage]

    # Type-only: the tui adapter is imported lazily inside `_tui` (see the note there), so
    # the post-menu handler can be typed without pulling Textual in at CLI startup.
    from generic_ml_wrapper.adapter.inbound.tui.menu_app import MenuChoice


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


def _add_guided_flags(parser: argparse.ArgumentParser) -> None:
    """Add the mutually-exclusive ``--guided`` / ``--quick`` authoring-depth flags.

    With neither, an interactive authoring command prompts for the choice; either flag
    answers it up front, so full argv never prompts.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--guided",
        action="store_true",
        help=i18n.t("cli.flag.guided"),
    )
    group.add_argument(
        "--quick",
        action="store_true",
        help=i18n.t("cli.flag.quick"),
    )


# The top-level subcommands. A first argv token that is none of these (and not a flag)
# is treated as a job name — `gmlw <job>` is shorthand for `gmlw start <job>`. Kept in
# sync with build_parser by a test.
_COMMANDS = frozenset(
    {
        "init",
        "start",
        "run",
        "jobs",
        "sessions",
        "export",
        "clients",
        "statusline",
        "tui",
        "workflow",
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
    "workflow": "workflow_command",
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
    """Return the line ``--version`` prints."""
    return build_render_version().execute()


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
        "--workflow",
        "-w",
        default=None,
        help=i18n.t("cli.flag.workflow"),
    )
    start.add_argument(
        "--client-args",
        default=None,
        help=i18n.t("cli.flag.client_args"),
    )

    run = sub.add_parser("run", help=i18n.t("cli.cmd.run"))
    run.add_argument(
        "workflow",
        nargs="?",
        default=None,
        help=i18n.t("cli.arg.run_workflow"),
    )
    run.add_argument(
        "--client",
        default=None,
        help=i18n.t("cli.flag.client"),
    )
    run.add_argument(
        "--client-args",
        default=None,
        help=i18n.t("cli.flag.client_args"),
    )

    # `jobs` and `sessions` stay list-first: their `delete` sub-action is optional, so a
    # bare `gmlw jobs` still lists. Deliberately *not* in `_SUBACTIONS` — that map makes a
    # command with no action print its help, which is right for `workflow` and wrong here.
    jobs = sub.add_parser("jobs", help=i18n.t("cli.cmd.jobs"))
    _add_json_flag(jobs)
    jobs_sub = jobs.add_subparsers(dest="jobs_command", metavar=i18n.t("cli.metavar.action"))
    jobs_delete = jobs_sub.add_parser("delete", help=i18n.t("cli.cmd.jobs_delete"))
    jobs_delete.add_argument("job", nargs="+", help=i18n.t("cli.arg.delete_jobs"))
    _add_yes_flag(jobs_delete)

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

    clients = sub.add_parser("clients", help=i18n.t("cli.cmd.clients"))
    _add_json_flag(clients)

    sub.add_parser("statusline", help=i18n.t("cli.cmd.statusline"))

    sub.add_parser("tui", help=i18n.t("cli.cmd.tui"))

    workflow = sub.add_parser("workflow", help=i18n.t("cli.cmd.workflow"))
    workflow_sub = workflow.add_subparsers(
        dest="workflow_command", metavar=i18n.t("cli.metavar.action")
    )
    new = workflow_sub.add_parser("new", help=i18n.t("cli.cmd.workflow_new"))
    new.add_argument(
        "label",
        nargs="?",
        default=None,
        help=i18n.t("cli.arg.workflow_label_optional"),
    )
    new.add_argument(
        "--description",
        default="",
        help=i18n.t("cli.flag.workflow_description"),
    )
    new.add_argument(
        "--client",
        default=None,
        help=i18n.t("cli.flag.client"),
    )
    _add_guided_flags(new)
    export_wf = workflow_sub.add_parser("export", help=i18n.t("cli.cmd.workflow_export"))
    export_wf.add_argument("name", help=i18n.t("cli.arg.workflow_name"))
    import_wf = workflow_sub.add_parser("import", help=i18n.t("cli.cmd.workflow_import"))
    import_wf.add_argument("archive", help=i18n.t("cli.arg.workflow_archive"))
    import_wf.add_argument(
        "--replace",
        action="store_true",
        help=i18n.t("cli.flag.workflow_replace"),
    )
    drafts_parser = workflow_sub.add_parser("drafts", help=i18n.t("cli.cmd.workflow_drafts"))
    _add_json_flag(drafts_parser)
    resume = workflow_sub.add_parser("resume", help=i18n.t("cli.cmd.workflow_resume"))
    resume.add_argument(
        "draft",
        nargs="?",
        default=None,
        help=i18n.t("cli.arg.draft_optional"),
    )
    edit = workflow_sub.add_parser("edit", help=i18n.t("cli.cmd.workflow_edit"))
    edit.add_argument("name", help=i18n.t("cli.arg.workflow_name"))
    edit.add_argument(
        "--resume-latest",
        action="store_true",
        help=i18n.t("cli.flag.resume_edit"),
    )
    edit.add_argument(
        "--client",
        default=None,
        help=i18n.t("cli.flag.client"),
    )
    _add_guided_flags(edit)
    workflow_list = workflow_sub.add_parser("list", help=i18n.t("cli.cmd.workflow_list"))
    _add_json_flag(workflow_list)

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
    creds_set.add_argument("workflow", help=i18n.t("cli.arg.creds_workflow"))
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


def format_jobs(summaries: list[JobSummary], loc: i18n.Localizer | None = None) -> str:
    """Render the job summaries as human-readable lines.

    Args:
        summaries: The job summaries to render.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not summaries:
        return loc.t("jobs.none")
    lines = [loc.t("jobs.count", count=len(summaries)), ""]
    width = max(len(summary.job) for summary in summaries)
    lines += [
        loc.t("jobs.row", job=f"{summary.job:<{width}}", count=summary.session_count)
        for summary in summaries
    ]
    return "\n".join(lines)


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
    for session, usage in zip(sessions, usages, strict=True):
        resumable = loc.t("clients.yes") if session.resumable else loc.t("clients.no")
        lines.append(
            loc.t(
                "sessions.row",
                session=f"{session.session_id:<{session_width}}",
                date=f"{(session.created_at or '')[:16]:<16}",  # YYYY-MM-DD HH:MM (blank if unset)
                client=f"{session.client:<{client_width}}",
                resumable=f"{resumable:<3}",
                usage=f"{usage:<{usage_width}}",
                folder=session.cwd or loc.t("sessions.no_folder"),
            )
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


def format_job_footprints(footprints: list[JobFootprint], loc: i18n.Localizer | None = None) -> str:
    """Render what deleting these jobs would remove.

    Shown before the confirmation, so "delete them?" is answered against the actual
    contents rather than a count of names.

    Args:
        footprints: One footprint per job, in the order they were asked for.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    lines = [loc.t("delete.jobs.preview", count=len(footprints)), ""]
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
    job: str, footprints: list[SessionFootprint], loc: i18n.Localizer | None = None
) -> str:
    """Render what deleting these sessions would remove.

    Args:
        job: The job the sessions belong to.
        footprints: One footprint per session, in the order they were asked for.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    lines = [loc.t("delete.sessions.preview", count=len(footprints), job=job), ""]
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
    if report.turn_count == 0 and not report.session_costs:
        return loc.t("usage.none", job=repr(report.job))
    width = max(
        (len(model.model) for model in report.models),
        default=len(_UNKNOWN_LABEL),
    )
    lines = [loc.t("usage.header", job=report.job, count=report.turn_count), ""]
    for turn in report.turns:
        lines.append(
            loc.t(
                "usage.turn_row",
                clock=_clock(turn.timestamp),
                model=f"{turn.model:<{width}}",
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


def _clock(timestamp: float) -> str:
    """Render an epoch timestamp as a local ``HH:MM:SS``, or a dash when unset."""
    if timestamp <= 0:
        return "--:--:--"
    return datetime.fromtimestamp(timestamp, tz=UTC).astimezone().strftime("%H:%M:%S")


def _tokens(input_tokens: int, output_tokens: int, cache_tokens: int, loc: i18n.Localizer) -> str:
    """Render a token triple as ``  <in>(+<cache> cache)+<out> tok`` for the report."""
    cache = loc.t("usage.cache", cache=cache_tokens) if cache_tokens else ""
    return loc.t("usage.tokens", input=input_tokens, cache=cache, output=output_tokens)


def format_drafts(drafts: list[Draft], loc: i18n.Localizer | None = None) -> str:
    """Render the unfinished authoring drafts as human-readable lines.

    Args:
        drafts: The drafts to render, newest first.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not drafts:
        return loc.t("draft.none")
    lines = [loc.t("draft.count", count=len(drafts)), ""]
    lines += [
        loc.t(
            "draft.row",
            draft=draft.key,
            state=loc.t("draft.finished" if draft.finished else "draft.unfinished"),
            name=draft.name or loc.t("draft.unnamed"),
        )
        for draft in drafts
    ]
    return "\n".join(lines)


def format_workflows(workflows: list[Workflow], loc: i18n.Localizer | None = None) -> str:
    """Render the runnable workflows as human-readable lines.

    Shows the slug the user types beside the label its author gave it. A workflow
    predating the sidecar has the two the same and no description, so it renders exactly
    as it always did.

    Args:
        workflows: The workflows to render, sorted by slug.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not workflows:
        return loc.t("workflow.none")
    lines = [loc.t("workflow.count", count=len(workflows)), ""]
    lines += [
        loc.t(
            "workflow.row",
            workflow=flow.slug,
            label="" if flow.label == flow.slug else flow.label,
            description=flow.description,
        ).rstrip()
        for flow in workflows
    ]
    return "\n".join(lines)


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
        _check_store_contract()
        return _dispatch(sys.argv[1:] if argv is None else argv)
    except DomainError as error:  # a refusal we phrased ourselves — say it, don't dump it
        print(_render_error(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(file=sys.stderr)  # a tidy newline after ^C, never a traceback
        return 130
    except Exception as error:  # noqa: BLE001  last resort: no traceback reaches the user
        print(i18n.t("error.unexpected", error=error), file=sys.stderr)
        return 1


def _check_store_contract() -> None:
    """Refuse to run if the shipped migrations cannot reach the schema this build needs."""
    build_check_store_contract().execute()


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
_HANDOVER_COMMANDS = frozenset({"start", "run", "tui"})
#: The same, for `workflow <action>` — authoring launches a client just as `start` does.
_HANDOVER_WORKFLOW_ACTIONS = frozenset({"new", "edit", "resume"})
# Accepted as "yes" when confirming a replacement, in either shipped language.
_AFFIRMATIVE = frozenset({"y", "yes", "o", "oui"})


def _hands_over_the_terminal(args: argparse.Namespace) -> bool:
    """Report whether this command cedes the terminal to another program.

    Args:
        args: The parsed arguments.

    Returns:
        True when a client (or the full-screen menu) will own the screen.
    """
    if args.command in _HANDOVER_COMMANDS:
        return True
    return args.command == "workflow" and (
        getattr(args, "workflow_command", None) in _HANDOVER_WORKFLOW_ACTIONS
    )


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
    if _incomplete_command_help(parser, args):  # e.g. `gmlw workflow` -> show its help
        return 0
    # The init gate: on a real command (not the statusline hot path or bare help), an
    # un-initialised or legacy install (`[init] version` absent) is funnelled through the
    # forced setup before the requested command runs. `gmlw init` is exempt — it *is* the
    # setup, run by the dispatch below; bootstrapping ahead of it would seed a config that
    # init then mistook for a legacy one. Once initialised, just ensure the layout.
    if args.command not in (None, "statusline", "help"):
        needs_init = build_application_settings().setup_needed()
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
    try:
        if args.command is None:  # bare `gmlw`: first run → init, thereafter → the index
            return _index()
        if args.command == "help":
            return _help(args)
        if args.command == "init":
            return _run_init()
        if args.command == "start":
            return _start(args)
        if args.command == "run":
            return _run(args)
        if args.command == "statusline":
            return _statusline()
        if args.command == "tui":
            return _tui()
        if args.command == "workflow":
            return _workflow(args)
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
        if args.command == "sessions" and args.sessions_command == "delete":
            return _sessions_delete(args)
        view = _view(args)  # the print-and-exit-0 commands (jobs, sessions, export)
    except (
        IdentifierError,
        ClientSettingsUnusableError,
        CredentialsUnusableError,
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


def _run_init() -> int:
    """Run the setup interview, then the layout/slug migrations — the ``gmlw init`` flow.

    Shared by the ``init`` command, the first-run funnel, and the TUI's Config → Setup verb.
    Re-running on an initialised install merges the answers into the existing config (never
    wipes). Returns ``0``.
    """
    _announce_init(build_init().execute())
    _announce_migration(build_migrate_layout().execute())
    _announce_slug_migration(build_migrate_slugs().execute())
    print(i18n.t("init.reinit_hint"), file=sys.stderr)  # how to re-run setup from the menu
    return 0


def _index() -> int:
    """Bare ``gmlw``: run the forced setup on a fresh install, else open the interactive menu.

    First run wins over everything — a brand-new user is funnelled through init before any
    menu. Once initialised, bare ``gmlw`` becomes the front door: on a terminal it opens the
    ``gmlw tui`` menu; off a terminal ``_tui`` falls back to the plain capability index, so a
    piped/scripted ``gmlw`` never blocks on a menu.
    """
    if build_application_settings().setup_needed():  # first run — setup wins over the menu
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
        summaries = build_list_jobs().execute()
        return _as_json([asdict(s) for s in summaries]) if as_json else format_jobs(summaries)
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
        matching ``workflow import``'s "nothing happened, and you asked for something".
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
    # The receipt: what stayed, in the rows the user already read before confirming.
    print(format_job_footprints(kept), file=sys.stderr)
    print(
        i18n.t(
            "delete.jobs.partial",
            removed=len(outcome) - len(kept),
            count=len(outcome),
            kept=len(kept),
        ),
        file=sys.stderr,
    )
    return 1


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
        The process exit code (``2`` when an id is unknown or the delete was declined).
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
    print(format_session_footprints(job, kept), file=sys.stderr)
    print(
        i18n.t(
            "delete.sessions.partial",
            removed=len(outcome) - len(kept),
            count=len(outcome),
            kept=len(kept),
            job=job,
        ),
        file=sys.stderr,
    )
    return 1


def _client(raw: str | None) -> str:
    """Resolve the client to wrap: the explicit ``--client``, else the config default."""
    return build_application_settings().resolve_client(raw)


def format_client_guidance(readiness: ClientReadiness, loc: i18n.Localizer | None = None) -> str:
    """Render install/login guidance for a client that cannot launch.

    Args:
        readiness: The not-ready verdict from the client check.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The guidance text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if readiness.missing is not None:
        info = readiness.missing
        lines = [
            loc.t("client.guidance.missing", client=repr(readiness.client), display=info.display),
            loc.t("client.guidance.install", command=readiness.install_command),
            loc.t("client.guidance.login", login=info.login_for(loc)),
        ]
        others = [name for name in readiness.installed if name != readiness.client]
        if others:
            lines.append(loc.t("client.guidance.use_other", other=others[0]))
    else:
        supported = ", ".join(info.name for info in build_list_supported_clients().execute())
        lines = [
            loc.t(
                "client.guidance.unsupported",
                client=repr(readiness.client),
                supported=supported,
            )
        ]
    if not readiness.installed:
        lines += ["", loc.t("client.guidance.none_installed")]
        commands = readiness.catalogue_install_commands
        width = max((len(name) for name, _ in commands), default=0)
        lines += [f"  {name:<{width}}  {command}" for name, command in commands]
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
    """Report whether a run can happen here, printing the guidance when it cannot."""
    return _render_launch_location(build_check_launch_location().execute())


def _preflight_resume_cwd(cwd: str | None) -> bool:
    """Report whether a resumed session's folder is still there, with guidance if not."""
    return _render_launch_location(build_check_launch_location().execute(cwd))


def _render_launch_location(location: LaunchLocation) -> bool:
    """Print what is wrong with where the run would happen, and say whether to go on.

    The verdict is the application's; naming the folder to the user is this side's.
    """
    if location.usable:
        return True
    if location.problem is LaunchLocationProblem.CURRENT_GONE:
        print(i18n.t("preflight.cwd_gone"), file=sys.stderr)
    else:
        print(i18n.t("preflight.resume_cwd_gone", cwd=location.folder), file=sys.stderr)
    return False


_MAX_STATUSLINE_BYTES = 1_000_000  # a client's status payload is small JSON; cap the read


def _statusline() -> int:
    # A status line must always degrade to a printable line, never raise: the client
    # renders this output in place of its own status, so a traceback would land on screen.
    try:
        payload = "" if sys.stdin.isatty() else sys.stdin.read(_MAX_STATUSLINE_BYTES)
        line = build_render_statusline().execute(payload)
    except Exception as error:  # noqa: BLE001  degrade to an empty line, never error at the client
        log.warning(i18n.t("log.status_render_failed", error=error))
        print()
        return 0
    print(line)
    return 0


def _farewell() -> str | None:
    """Return the parting line, or ``None`` when the companion is off."""
    return build_render_farewell().execute()


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
    workflow appear, and a changed setting show its new value.

    Returns:
        What the user asked for, or ``None`` if they quit.
    """
    from generic_ml_wrapper.adapter.inbound.tui.menu_app import (  # noqa: PLC0415  lazy: tui adapter
        Archiver,
        ClientChoice,
        ClientRow,
        ConfigCatalog,
        ConfigSetResult,
        ConfigSetting,
        CreateOutcome,
        Deleter,
        ImportAttempt,
        JobChoice,
        MenuApp,
        SessionChoice,
        SwitchChoice,
        Switcher,
        UsageView,
    )

    def _job_choices() -> list[JobChoice]:
        return [
            JobChoice(job=s.job, session_count=s.session_count) for s in build_list_jobs().execute()
        ]

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
        kept = [footprint for footprint in outcome if not footprint.removed]
        if not kept:
            return i18n.t("delete.jobs.done", count=len(outcome))
        return i18n.t(
            "delete.jobs.partial",
            removed=len(outcome) - len(kept),
            count=len(outcome),
            kept=len(kept),
        )

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
        kept = [footprint for footprint in outcome if not footprint.removed]
        if not kept:
            return i18n.t("delete.sessions.done", count=len(outcome), job=job)
        return i18n.t(
            "delete.sessions.partial",
            removed=len(outcome) - len(kept),
            count=len(outcome),
            kept=len(kept),
            job=job,
        )

    # Deleting is the one write the menu does without leaving: it asks in-app and calls
    # these, so the user stays on the list they are clearing instead of being returned to
    # the front door. The app still holds no port -- these closures do.
    deleter = Deleter(
        preview_jobs=_preview_jobs,
        delete_jobs=_delete_jobs_in_app,
        preview_sessions=_preview_sessions,
        delete_sessions=_delete_sessions_in_app,
    )

    def _export_in_app(name: str) -> str:
        try:
            return i18n.t("workflow.export.written", path=build_export_workflow().execute(name))
        except (WorkflowNameError, WorkflowNotFoundError) as error:
            return f"✗ {_render_error(error)}"

    def _install_in_app(archive: str, replace: bool) -> ImportAttempt:
        try:
            result = build_import_workflow().execute(archive, replace=replace)
        except (ArchiveUnreadableError, WorkflowNameError) as error:
            return ImportAttempt(f"✗ {_render_error(error)}")
        if result.outcome is ImportOutcome.REFUSED:
            # Not an error: the use case reports the clash instead of resolving it, so the
            # question can be asked. The menu turns this into a confirmation screen.
            return ImportAttempt(
                i18n.t("workflow.import.exists", name=result.name), needs_confirmation=True
            )
        if result.outcome is ImportOutcome.REPLACED:
            return ImportAttempt(
                i18n.t("workflow.import.replaced", name=result.name, backup=result.backup)
            )
        return ImportAttempt(i18n.t("workflow.import.done", name=result.name))

    archiver = Archiver(
        export=_export_in_app,
        install=_install_in_app,
        reload_workflows=lambda: build_list_workflow_catalog().execute(),
    )

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
    # reads the snapshot; a set goes through the same ConfigCommandsUseCase.set that
    # the CLI's `config set` uses
    # uses (values/defaults pre-rendered through _setting_value so the app stays format-free).
    loc = i18n.active()

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
        ]

    def _apply_setting(key: str, raw: str) -> ConfigSetResult:
        try:  # a value out of range keeps the editor open with the localised reason
            outcome = config_commands.set(key, raw)
        except InvalidSettingValueError as error:
            return ConfigSetResult(ok=False, message=_render_error(error))
        return ConfigSetResult(
            ok=True, message=_format_set_outcome(outcome), value=_setting_value(outcome.new, loc)
        )

    def _set_default_client(name: str) -> ConfigSetResult:  # Config → Clients: pick the default
        return _apply_setting("client.default", name)

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

    def _validate_workflow(name: str) -> str | None:  # empty is fine — named at the end
        if not name:
            return None
        try:
            WorkflowName(name)
        except IdentifierError:
            return t("tui.wf.invalid")
        return None

    # The menu opens on a *snapshot* of the default client, for the rows that mention it.
    # The launch re-reads it, because the user may have changed it in Config while the menu
    # was up -- resolving it once, here, would launch the client they just left.
    return MenuApp(
        _job_choices(),
        switchers=switchers,
        validate_job=_validate_job,
        validate_workflow=_validate_workflow,
        sessions_for=_sessions_for,
        usage_view=_usage_view,
        save_usage=_save_usage,
        workflows=build_list_workflow_catalog().execute(),
        rules=build_list_rules().execute,
        clients=_clients,
        set_default_client=_set_default_client,
        config=config_catalog,
        current_client=_client(None),
        deleter=deleter,
        reload_jobs=_job_choices,
        archiver=archiver,
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
    if choice.action == "run" and choice.workflow is not None:  # launch on the chosen workflow
        return _run_workflow(choice.workflow, client)
    if choice.action == "workflow_new":  # author a new workflow (name may be None -> proposed)
        return _new_workflow(choice.workflow, client, choice.guided)
    if choice.action == "workflow_edit" and choice.workflow is not None:
        return _edit_workflow(choice.workflow, client, choice.guided)
    if choice.job is None or choice.action not in ("start", "resume"):
        return 0
    resume = choice.action == "resume"
    picked_cwd: str | None = None
    if resume and choice.session is not None:  # a specific session relaunches in its own folder
        recorded = build_list_sessions().execute(choice.job)
        picked = next((s for s in recorded if s.session_id == choice.session), None)
        picked_cwd = picked.cwd if picked is not None else None
    return _tui_launch_job(choice.job, resume, choice.session, picked_cwd, client)


def _tui_launch_job(
    job: str, resume: bool, session: str | None, picked_cwd: str | None, client: str
) -> int:
    """Launch (or resume) a job from the TUI's choice — the hand-off after ``run()`` returns.

    Args:
        job: The job to launch.
        resume: Whether this reopens an existing session.
        session: The specific session id to resume, or ``None`` for the latest / a new one.
        picked_cwd: A resumed session's stored folder to relaunch in, or ``None``.
        client: The resolved client to wrap.

    Returns:
        The process exit code.
    """
    command = StartJobCommand(
        job=JobId(job),
        client=client,
        resume_latest=resume and session is None,  # a picked session wins over "latest"
        resume_session=session,
        workflow=None,
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
    try:
        result = build_start_job().execute(command)
    except (UnknownWorkflowError, ResumeNotSupportedError) as error:
        print(_render_error(error), file=sys.stderr)
        return 2
    _print_exit_receipt(result)
    return result.exit_code


def _start(args: argparse.Namespace) -> int:
    if args.job is None:  # `gmlw start` with no job — guide instead of an argparse dump
        print(i18n.t("start.needs_job"), file=sys.stderr)
        return 2
    workflow = None if args.workflow is None else str(args.workflow)
    client = _client(args.client)
    command = StartJobCommand(
        job=JobId(args.job),
        client=client,
        resume_latest=bool(args.resume_latest),
        workflow=workflow,
        client_args=args.client_args,
    )
    if not _preflight_cwd():  # deleted working directory — the client would crash on getcwd
        return 2
    if not _preflight_client(client):  # client not installed — guide, don't launch
        return 2
    # The free host greeting (when a companion persona is set) is now injected into the
    # session's context by StartJobUseCase, so the client renders it in-band — the launch-time
    # stderr greeting was structurally invisible once the client cleared the screen.
    # The client owns the terminal for the session: it handles Ctrl+C itself, and a
    # A kill/hangup is forwarded to the client by the caller adapter, so the run ends by
    # returning: teardown (relay stop + status-line restore) happens on the way out, and
    # gmlw never leaves its hook behind in the user's settings.
    try:
        result = build_start_job().execute(command)
    except (UnknownWorkflowError, ResumeNotSupportedError) as error:
        print(_render_error(error))
        return 2
    farewell = _farewell()
    if farewell:
        print(farewell, file=sys.stderr)
    _print_exit_receipt(result)  # the persistent return summary: cost, commands, one tip
    return result.exit_code


def _run(args: argparse.Namespace) -> int:
    """Run a workflow directly: the job is named after it and its sessions accumulate.

    ``gmlw run <workflow>`` is the recurring-procedure counterpart to ``gmlw start`` —
    equivalent to ``gmlw start <workflow> -w <workflow>``. With no workflow given it
    offers a chooser at a terminal (never off one), then echoes the one-liner so the
    interactive path teaches the fast one; full argv never prompts.
    """
    workflow = _resolve_workflow(args.workflow)
    if workflow is None:
        return 2
    return _run_workflow(workflow, _client(args.client), args.client_args)


def _run_workflow(workflow: str, client: str, client_args: str | None = None) -> int:
    """Launch the client on a workflow's own job — shared by ``gmlw run`` and the TUI Run verb.

    Args:
        workflow: The workflow to run (also the job name it accumulates sessions under).
        client: The resolved client to wrap.
        client_args: Passthrough launch arguments for this call, or ``None`` to use the
            client's configured value. The TUI passes ``None`` — it has no flag surface.

    Returns:
        The process exit code.
    """
    command = StartJobCommand(
        job=JobId(workflow),
        client=client,
        resume_latest=False,
        workflow=workflow,
        client_args=client_args,
    )
    if not _preflight_cwd():  # deleted working directory — the client would crash on getcwd
        return 2
    if not _preflight_client(client):  # client not installed — guide, don't launch
        return 2
    try:
        result = build_start_job().execute(command)
    except (UnknownWorkflowError, ResumeNotSupportedError) as error:
        print(_render_error(error))
        return 2
    farewell = _farewell()
    if farewell:
        print(farewell, file=sys.stderr)
    _print_exit_receipt(result)
    return result.exit_code


def _resolve_workflow(given: str | None) -> str | None:
    """Resolve the workflow to run: the given name, else an interactive choice.

    Args:
        given: The workflow named on the command line, or ``None``.

    Returns:
        The workflow name to run, or ``None`` when it could not be resolved (with
        guidance already printed to stderr).
    """
    if given is not None:
        return str(given)
    names = build_list_workflows().execute()
    if not names:  # nothing to run yet — point at authoring, not a picker with no options
        print(i18n.t("run.no_workflows"), file=sys.stderr)
        return None
    chosen = build_workflow_chooser().choose(names)
    if chosen is None:  # declined, or no terminal to prompt on
        print(i18n.t("run.needs_workflow"), file=sys.stderr)
        return None
    print(i18n.t("run.echo", workflow=chosen), file=sys.stderr)  # teach the fast path
    return chosen


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
        workflow = WorkflowName(args.workflow)
        name = EnvVarName(args.name)
        build_set_credential().execute(SetCredentialCommand(workflow=workflow, name=name))
        print(i18n.t("creds.stored", workflow=workflow, name=name))
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
        except UnknownSettingError:
            print(i18n.t("config.unknown_key", key=args.key), file=sys.stderr)
            return 2
        print(_as_json(_setting_payload(view)) if as_json else format_setting(view))
        return 0
    if args.config_command == "set":
        return _config_set(commands, args.key, args.value)
    return 0


def _config_set(commands: ConfigCommandsUseCase, key: str, value: str) -> int:
    try:
        outcome = commands.set(key, value)
    except UnknownSettingError:
        print(i18n.t("config.unknown_key", key=key), file=sys.stderr)
        return 2
    except InvalidSettingValueError as error:
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


def _workflow_drafts(args: argparse.Namespace) -> int:
    """List the unfinished authoring drafts."""
    drafts = build_list_drafts().execute()
    print(_as_json([asdict(d) for d in drafts]) if bool(args.json) else format_drafts(drafts))
    return 0


def _workflow_list(args: argparse.Namespace) -> int:
    """List the runnable workflows with the words behind their slugs."""
    flows = build_list_workflow_catalog().execute()
    print(
        _as_json([asdict(flow) for flow in flows]) if bool(args.json) else format_workflows(flows)
    )
    return 0


def _workflow(args: argparse.Namespace) -> int:
    """Dispatch a ``gmlw workflow <verb>``; an unknown or absent verb is a no-op."""
    handler = _WORKFLOW_VERBS.get(args.workflow_command)
    return handler(args) if handler is not None else 0


def _workflow_new(args: argparse.Namespace) -> int:
    """Author a new workflow (guide instead of launching when the client isn't ready).

    The name is optional — omit it and the authoring session proposes one at the end,
    after which gmlw deploys the draft. A name given up front is a seed that fails fast
    on a collision. The draft's fate on the return is reported from the result.
    """
    label = None if args.label is None else str(args.label)
    return _new_workflow(
        label, _client(args.client), _resolve_guided(args), description=str(args.description)
    )


def _new_workflow(label: str | None, client: str, guided: bool, *, description: str = "") -> int:
    """Author a new workflow — shared by ``gmlw workflow new`` and the TUI Create verb.

    Args:
        label: A suggested human name, or ``None`` to let the session settle on one at
            the end. Only a seed: the slug is derived from whatever the session chooses.
        client: The resolved client to wrap.
        guided: Whether to use the guided (facilitative) authoring experience.
        description: A fuller line to carry into the workflow, or empty.

    Returns:
        The process exit code.
    """
    if not _preflight_client(client):
        return 2
    try:
        result = build_new_workflow().execute(
            NewWorkflowCommand(label=label, client=client, guided=guided, description=description)
        )
    except WorkflowExistsError:  # a seed name that already exists — point at editing it
        print(i18n.t("workflow.new.exists", name=label), file=sys.stderr)
        return 2
    except WorkflowNameError as error:
        print(_render_error(error))
        return 2
    _announce_new_workflow(result)
    return result.exit_code


def _announce_new_workflow(result: NewWorkflowResult) -> None:
    """Report how an authoring session's draft resolved, on the return (to stderr)."""
    if result.outcome is WorkflowOutcome.DEPLOYED:
        print(i18n.t("workflow.new.deployed", name=result.name), file=sys.stderr)
    elif result.outcome is WorkflowOutcome.COLLISION:
        print(
            i18n.t("workflow.new.collision", name=result.name, draft=result.draft_path),
            file=sys.stderr,
        )
    else:  # INCOMPLETE — no finished marker; the draft is kept so nothing is lost
        print(i18n.t("workflow.new.incomplete", draft=result.draft_path), file=sys.stderr)


def _workflow_export(args: argparse.Namespace) -> int:
    """Pack a workflow into ``~/.gmlw/exports`` for sharing."""
    return _export_workflow(str(args.name))


def _export_workflow(name: str) -> int:
    """Export a workflow — shared by ``gmlw workflow export`` and the TUI Export verb.

    Args:
        name: The workflow's slug.

    Returns:
        The process exit code.
    """
    try:
        written = build_export_workflow().execute(name)
    except (WorkflowNameError, WorkflowNotFoundError) as error:
        print(_render_error(error))
        return 2
    print(i18n.t("workflow.export.written", path=written), file=sys.stderr)
    return 0


def _workflow_import(args: argparse.Namespace) -> int:
    """Install a workflow from an archive."""
    return _import_workflow(str(args.archive), replace=bool(args.replace))


def _import_workflow(archive: str, *, replace: bool = False) -> int:
    """Import a workflow — shared by ``gmlw workflow import`` and the TUI Import verb.

    The use case reports a name clash rather than resolving it, so the question is asked
    here where a person can answer it — and only when there is someone to ask. Off a tty
    the import is refused rather than silently overwriting.

    Args:
        archive: The archive to install from.
        replace: Displace an existing workflow of the same name without asking.

    Returns:
        The process exit code.
    """
    try:
        result = build_import_workflow().execute(archive, replace=replace)
        if result.outcome is ImportOutcome.REFUSED:
            if not _confirm_replace(result.name):
                print(i18n.t("workflow.import.kept", name=result.name), file=sys.stderr)
                return 2
            result = build_import_workflow().execute(archive, replace=True)
    except (ArchiveUnreadableError, WorkflowNameError) as error:
        print(_render_error(error))
        return 2
    if result.outcome is ImportOutcome.REPLACED:
        print(
            i18n.t("workflow.import.replaced", name=result.name, backup=result.backup),
            file=sys.stderr,
        )
    else:
        print(i18n.t("workflow.import.done", name=result.name), file=sys.stderr)
    return 0


def _confirm_replace(name: str) -> bool:
    """Ask whether to displace an existing workflow; ``False`` when nobody can answer."""
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        print(i18n.t("workflow.import.exists_no_tty", name=name), file=sys.stderr)
        return False
    print(i18n.t("workflow.import.exists", name=name), file=sys.stderr)
    return input(i18n.t("workflow.import.confirm")).strip().lower() in _AFFIRMATIVE


def _workflow_resume(args: argparse.Namespace) -> int:
    """Reopen an unfinished authoring draft — the named one, or the most recent.

    The client is not chosen here: a draft belongs to the session that made it, so the
    use case reopens it on that session's own client.
    """
    draft = None if args.draft is None else str(args.draft)
    try:
        result = build_new_workflow().execute(
            NewWorkflowCommand(
                label=None,
                client=_client(None),  # unused on a resume; the session carries its own
                resume_draft=draft,
                resume_latest=draft is None,
            )
        )
    except NoSuchDraftError as error:
        print(i18n.t("draft.cannot_resume", error=_render_error(error)), file=sys.stderr)
        return 2
    _announce_new_workflow(result)
    return result.exit_code


def _workflow_edit(args: argparse.Namespace) -> int:
    """Edit an existing workflow (guide instead of launching when the client isn't ready).

    Resuming skips the authoring-depth prompt: the guided choice was made when the edit
    started, and the reopened session already carries it.
    """
    resume = bool(args.resume_latest)
    guided = False if resume else _resolve_guided(args)
    return _edit_workflow(str(args.name), _client(args.client), guided, resume_latest=resume)


def _edit_workflow(name: str, client: str, guided: bool, *, resume_latest: bool = False) -> int:
    """Edit an existing workflow — shared by ``gmlw workflow edit`` and the TUI Edit verb.

    Args:
        name: The workflow to edit.
        client: The resolved client to wrap.
        guided: Whether to use the guided (facilitative) authoring experience.
        resume_latest: Reopen the workflow's most recent editing session instead of
            starting a fresh one. The client comes from that session, not from here.

    Returns:
        The process exit code.
    """
    if not _preflight_client(client) and not resume_latest:
        return 2
    try:
        command = EditWorkflowCommand(
            name=name, client=client, guided=guided, resume_latest=resume_latest
        )
        return build_edit_workflow().execute(command)
    except NoEditToResumeError as error:
        print(
            i18n.t("workflow.edit.nothing_to_resume", error=_render_error(error)), file=sys.stderr
        )
        return 2
    except (WorkflowNameError, WorkflowNotFoundError) as error:
        print(_render_error(error))
        return 2


_WORKFLOW_VERBS: dict[str, Callable[[argparse.Namespace], int]] = {
    "new": _workflow_new,
    "edit": _workflow_edit,
    "resume": _workflow_resume,
    "export": _workflow_export,
    "import": _workflow_import,
    "drafts": _workflow_drafts,
    "list": _workflow_list,
}


def _resolve_guided(args: argparse.Namespace) -> bool:
    """Resolve the authoring depth: the flag if given, else an interactive prompt.

    ``--guided`` / ``--quick`` answer up front (full argv never prompts). With neither, an
    interactive terminal is asked; off a terminal the chooser declines and we fall back to
    the lean interview.
    """
    if args.guided:
        return True
    if args.quick:
        return False
    return build_guided_chooser().choose() is AuthoringMode.GUIDED  # None (no TTY) → lean


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
