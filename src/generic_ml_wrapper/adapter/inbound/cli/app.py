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
from collections.abc import Generator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.cli.banner import banner
from generic_ml_wrapper.adapter.inbound.cli.help_topics import (
    TOPICS,
    render_topic,
    render_topic_list,
)
from generic_ml_wrapper.adapter.inbound.cli.hints import next_hint
from generic_ml_wrapper.adapter.inbound.cli.index import render_index
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_guided_chooser import GUIDED
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import SettingsUnreadableError
from generic_ml_wrapper.adapter.outbound.credentials.filesystem_credentials_store import (
    CredentialsUnreadableError,
)
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.domain.model.axis import AxisKind
from generic_ml_wrapper.application.domain.model.identifiers import (
    EnvVarName,
    IdentifierError,
    JobId,
    WorkflowName,
)
from generic_ml_wrapper.application.domain.model.migration import (
    MigrationReport,
    SlugMigrationReport,
)
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.plugin import Plugin
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
from generic_ml_wrapper.application.port.inbound.edit_workflow import (
    EditWorkflowCommand,
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.export_usage import UsageReport
from generic_ml_wrapper.application.port.inbound.init import InitOutcome
from generic_ml_wrapper.application.port.inbound.list_clients import ClientStatus
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary
from generic_ml_wrapper.application.port.inbound.list_sessions import SessionSummary
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflowCommand,
    NewWorkflowResult,
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
from generic_ml_wrapper.application.wiring.composition import (
    build_axis_catalog,
    build_bootstrap,
    build_check_client_ready,
    build_config_commands,
    build_create_axis,
    build_edit_workflow,
    build_export_usage,
    build_guided_chooser,
    build_init,
    build_list_clients,
    build_list_jobs,
    build_list_personas,
    build_list_plugins,
    build_list_sessions,
    build_list_workflows,
    build_localizer,
    build_migrate_layout,
    build_migrate_slugs,
    build_new_workflow,
    build_render_statusline,
    build_save_usage_report,
    build_set_credential,
    build_start_job,
    build_workflow_chooser,
)
from generic_ml_wrapper.common import config, i18n, paths, settings_registry
from generic_ml_wrapper.common.log import configure as configure_logging
from generic_ml_wrapper.common.log import log
from generic_ml_wrapper.common.spec_loader import SpecLoadError

if TYPE_CHECKING:
    # argparse does not publicly export the type ``add_subparsers`` returns; alias it once
    # (the private reference is confined here) so the parser-builder helpers can type it.
    _SubParsers = argparse._SubParsersAction[argparse.ArgumentParser]  # pyright: ignore[reportPrivateUsage]


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    """Add the shared ``--json`` flag to a read command's parser."""
    parser.add_argument("--json", action="store_true", help="output as JSON instead of text")


def _add_guided_flags(parser: argparse.ArgumentParser) -> None:
    """Add the mutually-exclusive ``--guided`` / ``--quick`` authoring-depth flags.

    With neither, an interactive authoring command prompts for the choice; either flag
    answers it up front, so full argv never prompts.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--guided",
        action="store_true",
        help="use the guided authoring experience (a facilitative guide; costs more)",
    )
    group.add_argument(
        "--quick",
        action="store_true",
        help="use the lean interview (skip the guided experience)",
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
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=_version_string())
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser(
        "init",
        help="set up gmlw (language, name, role, environment, persona, client)",
    )

    start = sub.add_parser("start", help="start or resume a session on a job")
    start.add_argument("job", nargs="?", default=None, help="the job identifier")
    start.add_argument(
        "--client",
        default=None,
        help="which client to wrap (default: the configured default, or claude)",
    )
    start.add_argument(
        "--resume-latest",
        action="store_true",
        help="resume the job's most recent session",
    )
    start.add_argument(
        "--workflow",
        "-w",
        default=None,
        help="run a workflow on the job (see: gmlw workflow list)",
    )

    run = sub.add_parser("run", help="run a workflow directly (the job is named after it)")
    run.add_argument(
        "workflow",
        nargs="?",
        default=None,
        help="the workflow to run (omit to choose one; see: gmlw workflow list)",
    )
    run.add_argument(
        "--client",
        default=None,
        help="which client to wrap (default: the configured default, or claude)",
    )

    jobs = sub.add_parser("jobs", help="list the jobs with recorded activity")
    _add_json_flag(jobs)

    sessions = sub.add_parser("sessions", help="list a job's sessions")
    sessions.add_argument("job", help="the job identifier")
    _add_json_flag(sessions)

    export = sub.add_parser("export", help="report a job's recorded usage")
    export.add_argument("job", help="the job identifier")
    _add_json_flag(export)

    clients = sub.add_parser("clients", help="list the supported clients and their versions")
    _add_json_flag(clients)

    sub.add_parser("statusline", help="render the status line (called by the client)")

    sub.add_parser("tui", help="open the interactive menu")

    workflow = sub.add_parser("workflow", help="author/list workflows")
    workflow_sub = workflow.add_subparsers(dest="workflow_command", metavar="<action>")
    new = workflow_sub.add_parser("new", help="author a new workflow (no job)")
    new.add_argument(
        "name",
        nargs="?",
        default=None,
        help="a suggested name (optional; the session proposes one at the end)",
    )
    new.add_argument(
        "--client",
        default=None,
        help="which client to wrap (default: the configured default, or claude)",
    )
    _add_guided_flags(new)
    edit = workflow_sub.add_parser("edit", help="edit an existing workflow (no job)")
    edit.add_argument("name", help="the workflow to edit")
    edit.add_argument(
        "--client",
        default=None,
        help="which client to wrap (default: the configured default, or claude)",
    )
    _add_guided_flags(edit)
    workflow_list = workflow_sub.add_parser("list", help="list the runnable workflows")
    _add_json_flag(workflow_list)

    persona = sub.add_parser("persona", help="list the selectable personas")
    persona_sub = persona.add_subparsers(dest="persona_command", metavar="<action>")
    persona_list = persona_sub.add_parser("list", help="list the selectable personas")
    _add_json_flag(persona_list)

    plugins = sub.add_parser("plugins", help="list the installed plugins")
    plugins_sub = plugins.add_subparsers(dest="plugins_command", metavar="<action>")
    plugins_list = plugins_sub.add_parser("list", help="list the installed plugins")
    _add_json_flag(plugins_list)

    creds = sub.add_parser("creds", help="manage per-workflow credentials")
    creds_sub = creds.add_subparsers(dest="creds_command", metavar="<action>")
    creds_set = creds_sub.add_parser("set", help="store a workflow credential")
    creds_set.add_argument("workflow", help="the workflow the credential belongs to")
    creds_set.add_argument("name", help="the environment-variable name to export at launch")

    _add_config_parser(sub)
    _add_axis_parsers(sub)
    _add_help_parser(sub)
    return parser


def _add_axis_parsers(sub: _SubParsers) -> None:
    """Add the ``environment`` and ``role`` commands (each with a ``new`` action)."""
    for command, noun in (("environment", "environment"), ("role", "role")):
        parser = sub.add_parser(command, help=f"create and manage {noun}s")
        action = parser.add_subparsers(dest=f"{command}_command", metavar="<action>")
        new = action.add_parser("new", help=f"create a new {noun}")
        new.add_argument("label", help="the human name (a slug is derived from it)")
        new.add_argument("--description", default="", help="a fuller line saved to its .about.toml")
        new.add_argument(
            "--default",
            action="store_true",
            dest="make_default",
            help=f"also make it the default {noun}",
        )


def _add_config_parser(sub: _SubParsers) -> None:
    """Add the ``config`` command (list/get/set) to the top-level subparsers."""
    config_parser = sub.add_parser("config", help="view or change gmlw settings")
    config_sub = config_parser.add_subparsers(dest="config_command", metavar="<action>")
    config_list = config_sub.add_parser("list", help="list every setting and its value")
    _add_json_flag(config_list)
    config_get = config_sub.add_parser("get", help="show one setting")
    config_get.add_argument("key", help="the dotted setting key (e.g. profile.default_role)")
    _add_json_flag(config_get)
    config_set = config_sub.add_parser("set", help="change one setting")
    config_set.add_argument("key", help="the dotted setting key")
    config_set.add_argument("value", help="the new value (use 'none' to clear an optional key)")


def _add_help_parser(sub: _SubParsers) -> None:
    """Add the ``help`` command (topic explainers) to the top-level subparsers."""
    help_parser = sub.add_parser("help", help="explain a core concept (see: gmlw help)")
    help_parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        metavar="<topic>",
        help=f"the concept to explain ({', '.join(TOPICS)}); omit to list the topics",
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
    width = max(len(session.session_id) for session in sessions)
    lines += [
        loc.t("sessions.row", session=f"{session.session_id:<{width}}", client=session.client)
        for session in sessions
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


def format_workflows(names: list[str], loc: i18n.Localizer | None = None) -> str:
    """Render the runnable workflow names as human-readable lines.

    Args:
        names: The workflow names to render.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    if not names:
        return loc.t("workflow.none")
    lines = [loc.t("workflow.count", count=len(names)), ""]
    lines += [f"  {name}" for name in names]
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


def _dispatch(resolved: list[str]) -> int:  # noqa: PLR0911, PLR0912  (a per-command dispatcher)
    parser = build_parser()
    args = parser.parse_args(_implicit_start(resolved))
    configure_logging(os.environ.get("GMLW_LOG_LEVEL") or config.log_level())
    # Bind the language the whole app speaks: every user string and log line renders
    # through this active localiser (seeded to English until now).
    i18n.set_active(build_localizer())
    if _incomplete_command_help(parser, args):  # e.g. `gmlw workflow` -> show its help
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
        view = _view(args)  # the print-and-exit-0 commands (jobs, sessions, export)
    except (
        IdentifierError,
        SettingsUnreadableError,
        CredentialsUnreadableError,
        SpecLoadError,
    ) as error:
        print(i18n.t("error.generic", error=error), file=sys.stderr)
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
            loc.t("client.guidance.login", login=info.login),
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


def _tui() -> int:  # noqa: PLR0911, PLR0915  (menu + preflights + launch, each with its own exit)
    """Run the interactive menu, then hand off to the client outside the event loop.

    The hand-off lives in the *ordering* here: the Textual app owns the terminal only while
    ``run()`` blocks. When the user picks a job, the app calls ``exit(choice)``; Textual
    restores the terminal as ``run()`` returns; and only *then* do we launch the client
    through the same ``build_start_job`` path every other command uses. Off a TTY we never
    build the app -- we fall back to the plain capability index, honouring the "non-TTY never
    blocks on a menu" contract.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return _capability_index()  # never the menu off a TTY; never recurse back into _index
    from generic_ml_wrapper.adapter.inbound.tui.menu_app import (  # noqa: PLC0415  lazy: tui adapter
        ClientRow,
        ConfigCatalog,
        ConfigSetResult,
        ConfigSetting,
        CreateOutcome,
        JobChoice,
        MenuApp,
        SessionChoice,
        SwitchChoice,
        Switcher,
        UsageView,
    )

    jobs = [
        JobChoice(job=s.job, session_count=s.session_count) for s in build_list_jobs().execute()
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
    # reads the snapshot; a set goes through the same ConfigCommands.set the CLI's `config set`
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
        except settings_registry.InvalidSettingValueError as error:
            return ConfigSetResult(ok=False, message=i18n.t("error.generic", error=error))
        return ConfigSetResult(
            ok=True, message=_format_set_outcome(outcome), value=_setting_value(outcome.new, loc)
        )

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

    client = _client(None)  # the default client (ignored on resume: the session carries its own)
    choice = MenuApp(
        jobs,
        switchers=switchers,
        validate_job=_validate_job,
        validate_workflow=_validate_workflow,
        sessions_for=_sessions_for,
        usage_view=_usage_view,
        save_usage=_save_usage,
        workflows=build_list_workflows().execute(),
        clients=_clients,
        config=config_catalog,
        current_client=client,
    ).run()  # blocks; terminal restored on return
    if choice is None:
        return 0
    if choice.action == "init":  # Config → Setup: re-run the interview on the restored terminal
        return _run_init()
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
        picked = next(
            (s for s in _sessions_for(choice.job) if s.session_id == choice.session), None
        )
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
    with _client_owns_interrupts():
        try:
            result = build_start_job().execute(command)
        except _Terminated:
            return 143
        except (UnknownWorkflowError, ResumeNotSupportedError) as error:
            print(i18n.t("error.generic", error=error), file=sys.stderr)
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
        except (UnknownWorkflowError, ResumeNotSupportedError) as error:
            print(i18n.t("error.generic", error=error))
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
    return _run_workflow(workflow, _client(args.client))


def _run_workflow(workflow: str, client: str) -> int:
    """Launch the client on a workflow's own job — shared by ``gmlw run`` and the TUI Run verb.

    Args:
        workflow: The workflow to run (also the job name it accumulates sessions under).
        client: The resolved client to wrap.

    Returns:
        The process exit code.
    """
    command = StartJobCommand(
        job=JobId(workflow),
        client=client,
        resume_latest=False,
        workflow=workflow,
    )
    if not _preflight_cwd():  # deleted working directory — the client would crash on getcwd
        return 2
    if not _preflight_client(client):  # client not installed — guide, don't launch
        return 2
    with _client_owns_interrupts():
        try:
            result = build_start_job().execute(command)
        except _Terminated:
            return 143  # 128 + SIGTERM: terminated, but teardown ran
        except (UnknownWorkflowError, ResumeNotSupportedError) as error:
            print(i18n.t("error.generic", error=error))
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
        print(i18n.t("error.generic", error=error), file=sys.stderr)
        return 2
    print(i18n.t("axis.created", kind=kind.value, label=result.label, slug=result.slug))
    if result.made_default:
        print(i18n.t("axis.made_default", kind=kind.value, slug=result.slug))
    return 0


def _creds(args: argparse.Namespace) -> int:
    if args.creds_command == "set":
        workflow = WorkflowName(args.workflow)
        name = EnvVarName(args.name)
        build_set_credential().execute(
            SetCredentialCommand(workflow=workflow, name=name, value=_read_secret())
        )
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
        print(i18n.t("error.generic", error=error), file=sys.stderr)
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


def _workflow(args: argparse.Namespace) -> int:
    if args.workflow_command == "new":
        return _workflow_new(args)
    if args.workflow_command == "edit":
        return _workflow_edit(args)
    if args.workflow_command == "list":
        names = build_list_workflows().execute()
        print(_as_json(names) if bool(args.json) else format_workflows(names))
        return 0
    return 0


def _workflow_new(args: argparse.Namespace) -> int:
    """Author a new workflow (guide instead of launching when the client isn't ready).

    The name is optional — omit it and the authoring session proposes one at the end,
    after which gmlw deploys the draft. A name given up front is a seed that fails fast
    on a collision. The draft's fate on the return is reported from the result.
    """
    name = None if args.name is None else str(args.name)
    return _new_workflow(name, _client(args.client), _resolve_guided(args))


def _new_workflow(name: str | None, client: str, guided: bool) -> int:
    """Author a new workflow — shared by ``gmlw workflow new`` and the TUI Create verb.

    Args:
        name: A suggested name, or ``None`` to let the session propose one at the end.
        client: The resolved client to wrap.
        guided: Whether to use the guided (facilitative) authoring experience.

    Returns:
        The process exit code.
    """
    if not _preflight_client(client):
        return 2
    try:
        result = build_new_workflow().execute(
            NewWorkflowCommand(name=name, client=client, guided=guided)
        )
    except WorkflowExistsError:  # a seed name that already exists — point at editing it
        print(i18n.t("workflow.new.exists", name=name), file=sys.stderr)
        return 2
    except WorkflowNameError as error:
        print(i18n.t("error.generic", error=error))
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


def _workflow_edit(args: argparse.Namespace) -> int:
    """Edit an existing workflow (guide instead of launching when the client isn't ready)."""
    return _edit_workflow(str(args.name), _client(args.client), _resolve_guided(args))


def _edit_workflow(name: str, client: str, guided: bool) -> int:
    """Edit an existing workflow — shared by ``gmlw workflow edit`` and the TUI Edit verb.

    Args:
        name: The workflow to edit.
        client: The resolved client to wrap.
        guided: Whether to use the guided (facilitative) authoring experience.

    Returns:
        The process exit code.
    """
    if not _preflight_client(client):
        return 2
    try:
        command = EditWorkflowCommand(name=name, client=client, guided=guided)
        return build_edit_workflow().execute(command)
    except (WorkflowNameError, WorkflowNotFoundError) as error:
        print(i18n.t("error.generic", error=error))
        return 2


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
    return build_guided_chooser().choose() == GUIDED  # None (no TTY) → lean


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
