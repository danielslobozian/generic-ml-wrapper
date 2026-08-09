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
from typing import TYPE_CHECKING, ClassVar

from generic_ml_wrapper.adapter.inbound.cli.banner import banner
from generic_ml_wrapper.adapter.inbound.cli.help_topics import (
    TOPICS,
    render_topic,
    render_topic_list,
)
from generic_ml_wrapper.adapter.inbound.common.action import (
    create_workflow,
    edit_workflow,
    resume_edit_workflow,
    run_init,
    run_workflow,
)
from generic_ml_wrapper.adapter.inbound.common.announcer import (
    print_create_workflow,
    print_exit_receipt,
    print_migration,
    print_slug_migration,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.language_change_interceptor import (
    LanguageChangeInterceptor,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
    MessageSourceAccessor,
    get_active,
    get_message,
)
from generic_ml_wrapper.adapter.inbound.common.launcher import (
    preflight_client,
    preflight_cwd,
)
from generic_ml_wrapper.adapter.inbound.common.renderer import (
    format_client_version,
    format_job_footprints,
    format_session_footprints,
    format_session_usage,
    format_set_outcome,
    format_setting_value,
    format_token_counts,
    get_farewell,
    render_error,
)
from generic_ml_wrapper.application.domain.model.archive_unreadable_error import (
    ArchiveUnreadableError,
)
from generic_ml_wrapper.application.domain.model.authoring_mode import AuthoringMode
from generic_ml_wrapper.application.domain.model.client_settings_unusable_error import (
    ClientSettingsUnusableError,
)
from generic_ml_wrapper.application.domain.model.credentials_unusable_error import (
    CredentialsUnusableError,
)
from generic_ml_wrapper.application.domain.model.draft import Draft
from generic_ml_wrapper.application.domain.model.env_var_name import EnvVarName
from generic_ml_wrapper.application.domain.model.environment_code_already_exists_error import (
    EnvironmentCodeAlreadyExistsError,
)
from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.invalid_setting_value_error import (
    InvalidSettingValueError,
)
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.no_such_draft_error import NoSuchDraftError
from generic_ml_wrapper.application.domain.model.no_such_job_error import NoSuchJobError
from generic_ml_wrapper.application.domain.model.no_such_session_error import NoSuchSessionError
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.domain.model.resume_not_supported_error import (
    ResumeNotSupportedError,
)
from generic_ml_wrapper.application.domain.model.role_code_already_exists_error import (
    RoleCodeAlreadyExistsError,
)
from generic_ml_wrapper.application.domain.model.uncodable_environment_label_error import (
    UncodableEnvironmentLabelError,
)
from generic_ml_wrapper.application.domain.model.uncodable_role_label_error import (
    UncodableRoleLabelError,
)
from generic_ml_wrapper.application.domain.model.unknown_setting_error import UnknownSettingError
from generic_ml_wrapper.application.domain.model.unknown_workflow_error import UnknownWorkflowError
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.domain.model.workflow_name import WorkflowName
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError
from generic_ml_wrapper.application.domain.model.workflow_not_found_error import (
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.add_environment_command import (
    AddEnvironmentCommand,
)
from generic_ml_wrapper.application.port.inbound.add_role_command import AddRoleCommand
from generic_ml_wrapper.application.port.inbound.config_commands import ConfigCommandsUseCase
from generic_ml_wrapper.application.port.inbound.create_job_command import CreateJobCommand
from generic_ml_wrapper.application.port.inbound.export_usage_query import ExportUsageQuery
from generic_ml_wrapper.application.port.inbound.find_job_query import FindJobQuery
from generic_ml_wrapper.application.port.inbound.import_outcome import ImportOutcome
from generic_ml_wrapper.application.port.inbound.job_summary import JobSummary
from generic_ml_wrapper.application.port.inbound.list_jobs_query import ListJobsQuery
from generic_ml_wrapper.application.port.inbound.listed_client import ListedClient
from generic_ml_wrapper.application.port.inbound.resume_create_workflow_command import (
    ResumeCreateWorkflowCommand,
)
from generic_ml_wrapper.application.port.inbound.resume_session_command import ResumeSessionCommand
from generic_ml_wrapper.application.port.inbound.session_summary import SessionSummary
from generic_ml_wrapper.application.port.inbound.set_credential_command import SetCredentialCommand
from generic_ml_wrapper.application.port.inbound.set_default_environment_command import (
    SetDefaultEnvironmentCommand,
)
from generic_ml_wrapper.application.port.inbound.set_default_role_command import (
    SetDefaultRoleCommand,
)
from generic_ml_wrapper.application.port.inbound.setting_view import SettingView
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult
from generic_ml_wrapper.application.port.inbound.start_new_session_command import (
    StartNewSessionCommand,
)
from generic_ml_wrapper.application.port.inbound.usage_report import UsageReport
from generic_ml_wrapper.application.wiring.composition import (
    build_add_environment,
    build_add_role,
    build_application_settings,
    build_bootstrap,
    build_compose_statusline,
    build_config_commands,
    build_create_job,
    build_delete_jobs,
    build_delete_sessions,
    build_describe_build,
    build_diagnostics,
    build_export_usage,
    build_export_workflow,
    build_find_job,
    build_guided_chooser,
    build_import_workflow,
    build_list_authoring_modes,
    build_list_clients,
    build_list_drafts,
    build_list_jobs,
    build_list_personas,
    build_list_plugins,
    build_list_sessions,
    build_list_workflow_catalog,
    build_list_workflows,
    build_migrate_layout,
    build_migrate_slugs,
    build_resume_create_workflow,
    build_resume_session_for_job,
    build_set_credential,
    build_set_default_environment,
    build_set_default_role,
    build_start_new_session_for_job,
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
        super().add_usage(usage, actions, groups, prefix or get_message("cli.section.usage"))

    def start_section(self, heading: str | None) -> None:
        """Open a section, translating argparse's own headings on the way through."""
        key = self._HEADINGS.get(heading or "")
        super().start_section(get_message(key) if key else heading)


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    """Add the shared ``--json`` flag to a read command's parser."""
    parser.add_argument("--json", action="store_true", help=get_message("cli.flag.json"))


def _add_yes_flag(parser: argparse.ArgumentParser) -> None:
    """Add the shared ``--yes`` flag to a delete command's parser."""
    parser.add_argument("--yes", action="store_true", help=get_message("cli.flag.yes"))


def _add_guided_flags(parser: argparse.ArgumentParser) -> None:
    """Add the mutually-exclusive ``--guided`` / ``--quick`` authoring-depth flags.

    With neither, an interactive authoring command prompts for the choice; either flag
    answers it up front, so full argv never prompts.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--guided",
        action="store_true",
        help=get_message("cli.flag.guided"),
    )
    group.add_argument(
        "--quick",
        action="store_true",
        help=get_message("cli.flag.quick"),
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
    return build_describe_build().execute()


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
    parser.add_argument("-h", "--help", action="help", help=get_message("cli.flag.help"))
    parser.add_argument(
        "--version",
        action="version",
        version=_version_string(),
        help=get_message("cli.flag.version"),
    )
    sub = parser.add_subparsers(dest="command", metavar=get_message("cli.metavar.command"))

    sub.add_parser(
        "init",
        help=get_message("cli.cmd.init"),
    )

    start = sub.add_parser("start", help=get_message("cli.cmd.start"))
    start.add_argument("job", nargs="?", default=None, help=get_message("cli.arg.job"))
    start.add_argument(
        "--client",
        default=None,
        help=get_message("cli.flag.client"),
    )
    start.add_argument(
        "--resume-latest",
        action="store_true",
        help=get_message("cli.flag.resume_latest"),
    )
    start.add_argument(
        "--workflow",
        "-w",
        default=None,
        help=get_message("cli.flag.workflow"),
    )
    start.add_argument(
        "--client-args",
        default=None,
        help=get_message("cli.flag.client_args"),
    )

    run = sub.add_parser("run", help=get_message("cli.cmd.run"))
    run.add_argument(
        "workflow",
        nargs="?",
        default=None,
        help=get_message("cli.arg.run_workflow"),
    )
    run.add_argument(
        "--client",
        default=None,
        help=get_message("cli.flag.client"),
    )
    run.add_argument(
        "--client-args",
        default=None,
        help=get_message("cli.flag.client_args"),
    )

    # `jobs` and `sessions` stay list-first: their `delete` sub-action is optional, so a
    # bare `gmlw jobs` still lists. Deliberately *not* in `_SUBACTIONS` — that map makes a
    # command with no action print its help, which is right for `workflow` and wrong here.
    jobs = sub.add_parser("jobs", help=get_message("cli.cmd.jobs"))
    _add_json_flag(jobs)
    jobs_sub = jobs.add_subparsers(dest="jobs_command", metavar=get_message("cli.metavar.action"))
    jobs_delete = jobs_sub.add_parser("delete", help=get_message("cli.cmd.jobs_delete"))
    jobs_delete.add_argument("job", nargs="+", help=get_message("cli.arg.delete_jobs"))
    _add_yes_flag(jobs_delete)

    sessions = sub.add_parser("sessions", help=get_message("cli.cmd.sessions"))
    sessions.add_argument("job", help=get_message("cli.arg.job"))
    _add_json_flag(sessions)
    sessions_sub = sessions.add_subparsers(
        dest="sessions_command", metavar=get_message("cli.metavar.action")
    )
    sessions_delete = sessions_sub.add_parser("delete", help=get_message("cli.cmd.sessions_delete"))
    sessions_delete.add_argument("session", nargs="+", help=get_message("cli.arg.delete_sessions"))
    _add_yes_flag(sessions_delete)

    export = sub.add_parser("export", help=get_message("cli.cmd.export"))
    export.add_argument("job", help=get_message("cli.arg.job"))
    _add_json_flag(export)

    clients = sub.add_parser("clients", help=get_message("cli.cmd.clients"))
    _add_json_flag(clients)

    sub.add_parser("statusline", help=get_message("cli.cmd.statusline"))

    workflow = sub.add_parser("workflow", help=get_message("cli.cmd.workflow"))
    workflow_sub = workflow.add_subparsers(
        dest="workflow_command", metavar=get_message("cli.metavar.action")
    )
    new = workflow_sub.add_parser("new", help=get_message("cli.cmd.workflow_new"))
    new.add_argument(
        "label",
        nargs="?",
        default=None,
        help=get_message("cli.arg.workflow_label_optional"),
    )
    new.add_argument(
        "--description",
        default="",
        help=get_message("cli.flag.workflow_description"),
    )
    new.add_argument(
        "--client",
        default=None,
        help=get_message("cli.flag.client"),
    )
    _add_guided_flags(new)
    export_wf = workflow_sub.add_parser("export", help=get_message("cli.cmd.workflow_export"))
    export_wf.add_argument("name", help=get_message("cli.arg.workflow_name"))
    import_wf = workflow_sub.add_parser("import", help=get_message("cli.cmd.workflow_import"))
    import_wf.add_argument("archive", help=get_message("cli.arg.workflow_archive"))
    import_wf.add_argument(
        "--replace",
        action="store_true",
        help=get_message("cli.flag.workflow_replace"),
    )
    drafts_parser = workflow_sub.add_parser("drafts", help=get_message("cli.cmd.workflow_drafts"))
    _add_json_flag(drafts_parser)
    resume = workflow_sub.add_parser("resume", help=get_message("cli.cmd.workflow_resume"))
    resume.add_argument(
        "draft",
        nargs="?",
        default=None,
        help=get_message("cli.arg.draft_optional"),
    )
    edit = workflow_sub.add_parser("edit", help=get_message("cli.cmd.workflow_edit"))
    edit.add_argument("name", help=get_message("cli.arg.workflow_name"))
    edit.add_argument(
        "--resume-latest",
        action="store_true",
        help=get_message("cli.flag.resume_edit"),
    )
    edit.add_argument(
        "--client",
        default=None,
        help=get_message("cli.flag.client"),
    )
    _add_guided_flags(edit)
    workflow_list = workflow_sub.add_parser("list", help=get_message("cli.cmd.workflow_list"))
    _add_json_flag(workflow_list)

    persona = sub.add_parser("persona", help=get_message("cli.cmd.persona"))
    persona_sub = persona.add_subparsers(
        dest="persona_command", metavar=get_message("cli.metavar.action")
    )
    persona_list = persona_sub.add_parser("list", help=get_message("cli.cmd.persona_list"))
    _add_json_flag(persona_list)

    plugins = sub.add_parser("plugins", help=get_message("cli.cmd.plugins"))
    plugins_sub = plugins.add_subparsers(
        dest="plugins_command", metavar=get_message("cli.metavar.action")
    )
    plugins_list = plugins_sub.add_parser("list", help=get_message("cli.cmd.plugins_list"))
    _add_json_flag(plugins_list)

    creds = sub.add_parser("creds", help=get_message("cli.cmd.creds"))
    creds_sub = creds.add_subparsers(
        dest="creds_command", metavar=get_message("cli.metavar.action")
    )
    creds_set = creds_sub.add_parser("set", help=get_message("cli.cmd.creds_set"))
    creds_set.add_argument("workflow", help=get_message("cli.arg.creds_workflow"))
    creds_set.add_argument("name", help=get_message("cli.arg.creds_name"))

    _add_config_parser(sub)
    _add_role_and_environment_parsers(sub)
    _add_help_parser(sub)
    return parser


def _add_role_and_environment_parsers(sub: _SubParsers) -> None:
    """Add the ``environment`` and ``role`` commands (each with a ``new`` action)."""
    # Keyed per side rather than interpolating a noun into one sentence: "create and
    # manage {noun}s" only pluralises in English, and French needs its own article and
    # agreement for each. Two of them is few enough to spell out honestly.
    for command in ("environment", "role"):
        parser = sub.add_parser(command, help=get_message(f"cli.cmd.{command}"))
        action = parser.add_subparsers(
            dest=f"{command}_command", metavar=get_message("cli.metavar.action")
        )
        new = action.add_parser("new", help=get_message(f"cli.cmd.{command}_new"))
        new.add_argument("label", help=get_message(f"cli.arg.{command}.label"))
        new.add_argument(
            "--description", default="", help=get_message(f"cli.flag.{command}.description")
        )
        new.add_argument(
            "--default",
            action="store_true",
            dest="make_default",
            help=get_message(f"cli.flag.{command}_default"),
        )


def _add_config_parser(sub: _SubParsers) -> None:
    """Add the ``config`` command (list/get/set) to the top-level subparsers."""
    config_parser = sub.add_parser("config", help=get_message("cli.cmd.config"))
    config_sub = config_parser.add_subparsers(
        dest="config_command", metavar=get_message("cli.metavar.action")
    )
    config_list = config_sub.add_parser("list", help=get_message("cli.cmd.config_list"))
    _add_json_flag(config_list)
    config_get = config_sub.add_parser("get", help=get_message("cli.cmd.config_get"))
    config_get.add_argument("key", help=get_message("cli.arg.config_key_example"))
    _add_json_flag(config_get)
    config_set = config_sub.add_parser("set", help=get_message("cli.cmd.config_set"))
    config_set.add_argument("key", help=get_message("cli.arg.config_key"))
    config_set.add_argument("value", help=get_message("cli.arg.config_value"))


def _add_help_parser(sub: _SubParsers) -> None:
    """Add the ``help`` command (topic explainers) to the top-level subparsers."""
    help_parser = sub.add_parser("help", help=get_message("cli.cmd.help"))
    help_parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        metavar=get_message("cli.metavar.topic"),
        help=get_message("cli.arg.help_topic", topics=", ".join(TOPICS)),
    )


def format_jobs(
    summaries: list[JobSummary], message_source: MessageSourceAccessor | None = None
) -> str:
    """Render the job summaries as human-readable lines.

    Args:
        summaries: The job summaries to render.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    if not summaries:
        return message_source.get_message("jobs.none")
    lines = [message_source.get_message("jobs.count", count=len(summaries)), ""]
    width = max(len(summary.job) for summary in summaries)
    lines += [
        message_source.get_message(
            "jobs.row", job=f"{summary.job:<{width}}", count=summary.session_count
        )
        for summary in summaries
    ]
    return "\n".join(lines)


def format_sessions(
    job: str, sessions: list[SessionSummary], message_source: MessageSourceAccessor | None = None
) -> str:
    """Render a job's sessions as human-readable lines.

    Args:
        job: The job the sessions belong to.
        sessions: The session summaries to render.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    if not sessions:
        return message_source.get_message("sessions.none", job=repr(job), start_job=job)
    lines = [message_source.get_message("sessions.count", job=job, count=len(sessions)), ""]
    session_width = max(len(session.session_id) for session in sessions)
    client_width = max(len(session.client) for session in sessions)
    usages = [format_session_usage(session, message_source) for session in sessions]
    usage_width = max(len(usage) for usage in usages)
    for session, usage in zip(sessions, usages, strict=True):
        resumable = (
            message_source.get_message("clients.yes")
            if session.resumable
            else message_source.get_message("clients.no")
        )
        lines.append(
            message_source.get_message(
                "sessions.row",
                session=f"{session.session_id:<{session_width}}",
                date=f"{(session.created_at or '')[:16]:<16}",  # YYYY-MM-DD HH:MM (blank if unset)
                client=f"{session.client:<{client_width}}",
                resumable=f"{resumable:<3}",
                usage=f"{usage:<{usage_width}}",
                folder=session.cwd or message_source.get_message("sessions.no_folder"),
            )
        )
    return "\n".join(lines)


def format_usage(report: UsageReport, message_source: MessageSourceAccessor | None = None) -> str:
    """Render a job's usage report: per-turn rows, totals by model, cost, and totals.

    Args:
        report: The usage report to render.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    if report.turn_count == 0 and not report.session_costs:
        return message_source.get_message("usage.none", job=repr(report.job))
    width = max(
        (len(model.model) for model in report.models),
        default=len(_UNKNOWN_LABEL),
    )
    lines = [
        message_source.get_message("usage.header", job=report.job, count=report.turn_count),
        "",
    ]
    for turn in report.turns:
        lines.append(
            message_source.get_message(
                "usage.turn_row",
                clock=_clock(turn.timestamp),
                model=f"{turn.model:<{width}}",
                duration=f"{turn.duration_s:>5.1f}",
                tokens=format_token_counts(
                    turn.input_tokens, turn.output_tokens, turn.cache_tokens, message_source
                ),
                turn_id=turn.turn_id or "-",
            )
        )
    if report.models:
        lines += ["", message_source.get_message("usage.totals_by_model")]
        lines += [
            message_source.get_message(
                "usage.model_row",
                model=f"{model.model:<{width}}",
                calls=f"{model.calls:>3}",
                tokens=format_token_counts(
                    model.input_tokens, model.output_tokens, model.cache_tokens, message_source
                ),
                duration=f"{model.duration_s:.1f}",
            )
            for model in report.models
        ]
    if report.session_costs:
        lines += ["", message_source.get_message("usage.cost_by_session")]
        lines += [
            message_source.get_message(
                "usage.cost_row", session=cost.session_id, cost=f"{cost.cost_usd:.2f}"
            )
            for cost in report.session_costs
        ]
    lines += [
        "",
        message_source.get_message(
            "usage.total",
            count=report.turn_count,
            tokens=format_token_counts(
                report.input_tokens, report.output_tokens, report.cache_tokens, message_source
            ),
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


def format_drafts(drafts: list[Draft], message_source: MessageSourceAccessor | None = None) -> str:
    """Render the unfinished authoring drafts as human-readable lines.

    Args:
        drafts: The drafts to render, newest first.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    if not drafts:
        return message_source.get_message("draft.none")
    lines = [message_source.get_message("draft.count", count=len(drafts)), ""]
    lines += [
        message_source.get_message(
            "draft.row",
            draft=draft.key,
            state=message_source.get_message(
                "draft.finished" if draft.finished else "draft.unfinished"
            ),
            name=draft.name or message_source.get_message("draft.unnamed"),
        )
        for draft in drafts
    ]
    return "\n".join(lines)


def format_workflows(
    workflows: list[Workflow], message_source: MessageSourceAccessor | None = None
) -> str:
    """Render the runnable workflows as human-readable lines.

    Shows the slug the user types beside the label its author gave it. A workflow
    predating the sidecar has the two the same and no description, so it renders exactly
    as it always did.

    Args:
        workflows: The workflows to render, sorted by slug.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    if not workflows:
        return message_source.get_message("workflow.none")
    lines = [message_source.get_message("workflow.count", count=len(workflows)), ""]
    lines += [
        message_source.get_message(
            "workflow.row",
            workflow=flow.slug,
            label="" if flow.label == flow.slug else flow.label,
            description=flow.description,
        ).rstrip()
        for flow in workflows
    ]
    return "\n".join(lines)


def format_personas(
    personas: list[Persona], message_source: MessageSourceAccessor | None = None
) -> str:
    """Render the selectable personas as human-readable lines.

    Args:
        personas: The personas to render.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    if not personas:
        return message_source.get_message("persona.none")
    lines = [message_source.get_message("persona.count", count=len(personas)), ""]
    width = max(len(persona.name) for persona in personas)
    lines += [
        message_source.get_message(
            "persona.row", name=f"{persona.name:<{width}}", description=persona.description
        )
        for persona in personas
    ]
    return "\n".join(lines)


def format_plugins(
    plugins: list[Plugin], message_source: MessageSourceAccessor | None = None
) -> str:
    """Render the installed plugins as human-readable lines.

    Args:
        plugins: The plugins to render.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    if not plugins:
        return message_source.get_message("plugins.none")
    lines = [message_source.get_message("plugins.count", count=len(plugins)), ""]
    width = max(len(plugin.plugin_id) for plugin in plugins)
    lines += [
        message_source.get_message(
            "plugins.row", plugin=f"{plugin.plugin_id:<{width}}", description=plugin.description
        )
        for plugin in plugins
    ]
    return "\n".join(lines)


def format_clients(
    statuses: list[ListedClient], message_source: MessageSourceAccessor | None = None
) -> str:
    """Render the supported clients as human-readable lines: version, resume, default.

    Args:
        statuses: The client statuses to render, in catalog order.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    lines = [message_source.get_message("clients.count", count=len(statuses)), ""]
    versions = [format_client_version(status, message_source) for status in statuses]
    name_width = max(len(status.display) for status in statuses)
    version_width = max(len(version) for version in versions)
    for status, version in zip(statuses, versions, strict=True):
        resumable = (
            message_source.get_message("clients.yes")
            if status.resumable
            else message_source.get_message("clients.no")
        )
        if status.resume_hint:  # a yes with a condition on it (codex: only once bound)
            resumable += f" ({message_source.get_message(status.resume_hint)})"
        default = message_source.get_message("clients.default") if status.is_default else ""
        lines.append(
            message_source.get_message(
                "clients.row",
                client=f"{status.display:<{name_width}}",
                version=f"{version:<{version_width}}",
                resumable=resumable,
                default=default,
            )
        )
    return "\n".join(lines)


def cli_main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    return _dispatch(sys.argv[1:] if argv is None else argv)


#: Commands after which another program owns the terminal — a client takes it over, or
#: the TUI paints a full-screen surface. Diagnostics must not go to stderr for these:
#: stderr is that program's screen, so a line written there corrupts its display and is
#: gone on the next redraw. They go to the rolling log file only (issue #59).
_HANDOVER_COMMANDS = frozenset({"start", "run"})
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
            run_init()
        elif not needs_init:
            build_bootstrap().execute()
        # Wrap the old profile/company layout into the active environment. Runs after init
        # has persisted the environment (or reads the existing one), once per command, and
        # is a no-op once the old layout is gone — catching installs initialised before the
        # migration existed. The `init` command runs its own below (after it writes config).
        if args.command != "init":
            print_migration(build_migrate_layout().execute())
            print_slug_migration(build_migrate_slugs().execute())
    try:
        if args.command == "help":
            return _help(args)
        if args.command == "init":
            return run_init()
        if args.command == "start":
            return _start(args)
        if args.command == "run":
            return _run(args)
        if args.command == "statusline":
            return _statusline()
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
            return _environment(args.environment_command, args)
        if args.command == "role":
            return _role(args.role_command, args)
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
        print(render_error(error), file=sys.stderr)
        return 2
    if view is None:
        parser.print_help()
    else:
        print(view)
    return 0


def _help(args: argparse.Namespace) -> int:
    """``gmlw help`` lists the topics; ``gmlw help <topic>`` explains one."""
    message_source = get_active()
    if args.topic is None:
        print(render_topic_list(message_source))
        return 0
    body = render_topic(message_source, args.topic)
    if body is None:
        print(get_message("help.unknown", topic=args.topic), file=sys.stderr)
        return 2
    print(body)
    return 0


def _view(args: argparse.Namespace) -> str | None:
    """Render a read-only command's output, or ``None`` if it isn't one."""
    as_json = bool(getattr(args, "json", False))
    if args.command == "jobs":
        summaries = build_list_jobs().execute(ListJobsQuery())
        return _as_json([asdict(s) for s in summaries]) if as_json else format_jobs(summaries)
    if args.command == "sessions":
        job = JobId(args.job)
        sessions = build_list_sessions().execute(job)
        if as_json:
            return _as_json([asdict(s) for s in sessions])
        return format_sessions(job, sessions)
    if args.command == "export":
        job = JobId(args.job)
        report = build_export_usage().execute(ExportUsageQuery(job=str(job)))
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
        print(get_message("delete.no_tty"), file=sys.stderr)
        return False
    return input(get_message("delete.confirm")).strip().lower() in _AFFIRMATIVE


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
        print(render_error(error), file=sys.stderr)
        return 2
    if not _confirm_delete(format_job_footprints(footprints), assume_yes=assume_yes):
        print(get_message("delete.cancelled"), file=sys.stderr)
        return 2
    outcome = delete.execute(jobs)
    kept = [footprint for footprint in outcome if not footprint.removed]
    if not kept:
        print(get_message("delete.jobs.done", count=len(outcome)), file=sys.stderr)
        return 0
    # The receipt: what stayed, in the rows the user already read before confirming.
    print(format_job_footprints(kept), file=sys.stderr)
    print(
        get_message(
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
        print(render_error(error), file=sys.stderr)
        return 2
    if not _confirm_delete(format_session_footprints(job, footprints), assume_yes=assume_yes):
        print(get_message("delete.cancelled"), file=sys.stderr)
        return 2
    outcome = delete.execute(job, sessions)
    kept = [footprint for footprint in outcome if not footprint.removed]
    if not kept:
        print(get_message("delete.sessions.done", count=len(outcome), job=job), file=sys.stderr)
        return 0
    print(format_session_footprints(job, kept), file=sys.stderr)
    print(
        get_message(
            "delete.sessions.partial",
            removed=len(outcome) - len(kept),
            count=len(outcome),
            kept=len(kept),
            job=job,
        ),
        file=sys.stderr,
    )
    return 1


_MAX_STATUSLINE_BYTES = 1_000_000  # a client's status payload is small JSON; cap the read


def _statusline() -> int:
    # A status line must always degrade to a printable line, never raise: the client
    # renders this output in place of its own status, so a traceback would land on screen.
    try:
        payload = "" if sys.stdin.isatty() else sys.stdin.read(_MAX_STATUSLINE_BYTES)
        line = build_compose_statusline().execute(payload)
    except Exception as error:  # noqa: BLE001  degrade to an empty line, never error at the client
        log.warning(f"status line render failed: {error}")
        print()
        return 0
    print(line)
    return 0


def _start(args: argparse.Namespace) -> int:
    if args.job is None:  # `gmlw start` with no job — guide instead of an argparse dump
        print(get_message("start.needs_job"), file=sys.stderr)
        return 2
    workflow = None if args.workflow is None else str(args.workflow)
    client = build_application_settings().resolve_client(args.client)
    if not preflight_cwd():  # deleted working directory — the client would crash on getcwd
        return 2
    if not preflight_client(client):  # client not installed — guide, don't launch
        return 2
    # The free host greeting (when a companion persona is set) is now injected into the
    # session's context by StartJobUseCase, so the client renders it in-band — the launch-time
    # stderr greeting was structurally invisible once the client cleared the screen.
    # The client owns the terminal for the session: it handles Ctrl+C itself, and a
    # A kill/hangup is forwarded to the client by the caller adapter, so the run ends by
    # returning: teardown (relay stop + status-line restore) happens on the way out, and
    # gmlw never leaves its hook behind in the user's settings.
    try:
        result = _launch_for_the_command_line(args, client, workflow)
    except (
        NoSuchJobError,
        NoSuchSessionError,
        UnknownWorkflowError,
        ResumeNotSupportedError,
    ) as error:
        print(render_error(error))
        return 2
    print(get_farewell(), file=sys.stderr)
    print_exit_receipt(result)  # the persistent return summary: cost, commands, one tip
    return result.exit_code


def _launch_for_the_command_line(
    args: argparse.Namespace, client: str, workflow: str | None
) -> StartJobResult:
    """Run what ``gmlw start`` asked for: the job's latest session, or a fresh one.

    Args:
        args: The parsed arguments, read for ``job``, ``resume_latest`` and ``client_args``.
        client: The resolved client, used only when starting fresh.
        workflow: The workflow to run, or ``None``.

    Returns:
        The run's outcome.

    Raises:
        NoSuchJobError: When ``--resume-latest`` names a job that does not exist.
        NoSuchSessionError: When that job has never run.
    """
    job = str(JobId(args.job))
    if args.resume_latest:
        found = build_find_job().execute(FindJobQuery(job=job))
        return build_resume_session_for_job().execute(
            ResumeSessionCommand(session=found.latest_session(), client_args=args.client_args)
        )
    # Create-then-start: `gmlw start <new-name>` still works, the job simply comes into
    # being through the use case that owns it rather than as a side effect of recording.
    build_create_job().execute(CreateJobCommand(job=job))
    return build_start_new_session_for_job().execute(
        StartNewSessionCommand(
            job=job, client=client, workflow=workflow, client_args=args.client_args
        )
    )


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
    return run_workflow(
        workflow, build_application_settings().resolve_client(args.client), args.client_args
    )


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
        print(get_message("run.no_workflows"), file=sys.stderr)
        return None
    chosen = build_workflow_chooser().choose(names)
    if chosen is None:  # declined, or no terminal to prompt on
        print(get_message("run.needs_workflow"), file=sys.stderr)
        return None
    print(get_message("run.echo", workflow=chosen), file=sys.stderr)  # teach the fast path
    return chosen


def _role(subcommand: str | None, args: argparse.Namespace) -> int:
    """Create a role from a typed label (``role new``).

    Making it the default is a second use case, called here: adding a role and choosing
    the default are two jobs, and one command asking for both does not make them one.

    Args:
        subcommand: The chosen sub-action (only ``new`` today; ``None`` is handled upstream
            by the incomplete-command help).
        args: The parsed arguments (label, description, make_default).

    Returns:
        ``0`` on success, ``2`` on an uncodable label or a code already taken.
    """
    if subcommand != "new":
        return 0
    try:
        result = build_add_role().execute(
            AddRoleCommand(label=args.label, description=args.description)
        )
    except (UncodableRoleLabelError, RoleCodeAlreadyExistsError) as error:
        print(render_error(error), file=sys.stderr)
        return 2
    print(get_message("role.created", label=result.role.label, code=result.role.code))
    if args.make_default:
        build_set_default_role().execute(SetDefaultRoleCommand(code=result.role.code))
        print(get_message("role.made_default", code=result.role.code))
    return 0


def _environment(subcommand: str | None, args: argparse.Namespace) -> int:
    """Create an environment from a typed label (``environment new``).

    Making it the default is a second use case, called here: adding an environment and
    choosing the default are two jobs, and one command asking for both does not make
    them one.

    Args:
        subcommand: The chosen sub-action (only ``new`` today; ``None`` is handled upstream
            by the incomplete-command help).
        args: The parsed arguments (label, description, make_default).

    Returns:
        ``0`` on success, ``2`` on an uncodable label or a code already taken.
    """
    if subcommand != "new":
        return 0
    try:
        result = build_add_environment().execute(
            AddEnvironmentCommand(label=args.label, description=args.description)
        )
    except (UncodableEnvironmentLabelError, EnvironmentCodeAlreadyExistsError) as error:
        print(render_error(error), file=sys.stderr)
        return 2
    print(
        get_message(
            "environment.created",
            label=result.environment.label,
            code=result.environment.code,
        )
    )
    if args.make_default:
        build_set_default_environment().execute(
            SetDefaultEnvironmentCommand(code=result.environment.code)
        )
        print(get_message("environment.made_default", code=result.environment.code))
    return 0


def _creds(args: argparse.Namespace) -> int:
    if args.creds_command == "set":
        workflow = WorkflowName(args.workflow)
        name = EnvVarName(args.name)
        build_set_credential().execute(SetCredentialCommand(workflow=workflow, name=name))
        print(get_message("creds.stored", workflow=workflow, name=name))
        return 0
    return 0


def format_setting_list(
    views: list[SettingView], message_source: MessageSourceAccessor | None = None
) -> str:
    """Render every setting with its current value and description (aligned).

    Args:
        views: The settings to render, in registry order.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    lines = [message_source.get_message("config.list.header", count=len(views)), ""]
    width = max((len(view.key) for view in views), default=0)
    for view in views:
        lines.append(
            message_source.get_message(
                "config.row",
                key=f"{view.key:<{width}}",
                value=format_setting_value(view.value, message_source),
            )
        )
        lines.append(message_source.get_message("config.row_desc", description=view.description))
    return "\n".join(lines)


def format_setting(view: SettingView, message_source: MessageSourceAccessor | None = None) -> str:
    """Render a single setting: value, description, default and any allowed values.

    Args:
        view: The setting to render.
        message_source: The message source to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    message_source = message_source or get_active()
    lines = [
        message_source.get_message(
            "config.get", key=view.key, value=format_setting_value(view.value, message_source)
        ),
        message_source.get_message("config.get_desc", description=view.description),
        message_source.get_message(
            "config.get_default", default=format_setting_value(view.default, message_source)
        ),
    ]
    if view.choices is not None:
        lines.append(
            message_source.get_message("config.get_allowed", choices=", ".join(view.choices))
        )
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
            print(get_message("config.unknown_key", key=args.key), file=sys.stderr)
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
        print(get_message("config.unknown_key", key=key), file=sys.stderr)
        return 2
    except InvalidSettingValueError as error:
        print(render_error(error), file=sys.stderr)
        return 2
    LanguageChangeInterceptor.after_setting_written(key, value)
    print(format_set_outcome(outcome))
    return 0


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
    return create_workflow(
        label,
        build_application_settings().resolve_client(args.client),
        _resolve_guided(args),
        description=str(args.description),
    )


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
        print(render_error(error))
        return 2
    print(get_message("workflow.export.written", path=written), file=sys.stderr)
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
                print(get_message("workflow.import.kept", name=result.name), file=sys.stderr)
                return 2
            result = build_import_workflow().execute(archive, replace=True)
    except (ArchiveUnreadableError, WorkflowNameError) as error:
        print(render_error(error))
        return 2
    if result.outcome is ImportOutcome.REPLACED:
        print(
            get_message("workflow.import.replaced", name=result.name, backup=result.backup),
            file=sys.stderr,
        )
    else:
        print(get_message("workflow.import.done", name=result.name), file=sys.stderr)
    return 0


def _confirm_replace(name: str) -> bool:
    """Ask whether to displace an existing workflow; ``False`` when nobody can answer."""
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        print(get_message("workflow.import.exists_no_tty", name=name), file=sys.stderr)
        return False
    print(get_message("workflow.import.exists", name=name), file=sys.stderr)
    return input(get_message("workflow.import.confirm")).strip().lower() in _AFFIRMATIVE


def _workflow_resume(args: argparse.Namespace) -> int:
    """Reopen an unfinished authoring draft — the named one, or the most recent.

    The client is not chosen here: a draft belongs to the session that made it, so the
    use case reopens it on that session's own client.
    """
    draft = None if args.draft is None else str(args.draft)
    try:
        result = build_resume_create_workflow().execute(
            ResumeCreateWorkflowCommand(draft_key=draft)
        )
    except NoSuchDraftError as error:
        print(get_message("draft.cannot_resume", error=render_error(error)), file=sys.stderr)
        return 2
    print_create_workflow(result)
    return result.exit_code


def _workflow_edit(args: argparse.Namespace) -> int:
    """Edit an existing workflow (guide instead of launching when the client isn't ready).

    Resuming skips the authoring-depth prompt: the guided choice was made when the edit
    started, and the reopened session already carries it.
    """
    if args.resume_latest:
        # No authoring-depth prompt and no client: the guided choice was made when the
        # edit started, and the reopened session carries both.
        return resume_edit_workflow(str(args.name))
    return edit_workflow(
        str(args.name),
        build_application_settings().resolve_client(args.client),
        _resolve_guided(args),
    )


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
    modes = build_list_authoring_modes().execute()
    return build_guided_chooser().choose(modes) is AuthoringMode.GUIDED  # None (no TTY) → lean


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
