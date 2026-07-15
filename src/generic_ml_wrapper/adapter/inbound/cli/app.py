# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The argparse command-line inbound adapter."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime

from generic_ml_wrapper.adapter.inbound.cli.banner import banner
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import SettingsUnreadableError
from generic_ml_wrapper.adapter.outbound.credentials.filesystem_credentials_store import (
    CredentialsUnreadableError,
)
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.domain.model.identifiers import (
    EnvVarName,
    IdentifierError,
    JobId,
    WorkflowName,
)
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.port.inbound.check_client_ready import ClientReadiness
from generic_ml_wrapper.application.port.inbound.export_usage import UsageReport
from generic_ml_wrapper.application.port.inbound.first_run_init import FirstRunOutcome
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary
from generic_ml_wrapper.application.port.inbound.list_sessions import SessionSummary
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflowCommand,
    WorkflowExistsError,
    WorkflowNameError,
)
from generic_ml_wrapper.application.port.inbound.set_credential import SetCredentialCommand
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJobCommand,
    UnknownWorkflowError,
)
from generic_ml_wrapper.application.wiring.composition import (
    build_bootstrap,
    build_check_client_ready,
    build_export_usage,
    build_first_run_init,
    build_list_jobs,
    build_list_personas,
    build_list_sessions,
    build_list_workflows,
    build_new_workflow,
    build_render_greeting,
    build_render_statusline,
    build_set_credential,
    build_start_job,
)
from generic_ml_wrapper.common import config
from generic_ml_wrapper.common.log import configure as configure_logging
from generic_ml_wrapper.common.spec_loader import SpecLoadError


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    """Add the shared ``--json`` flag to a read command's parser."""
    parser.add_argument("--json", action="store_true", help="output as JSON instead of text")


# The top-level subcommands. A first argv token that is none of these (and not a flag)
# is treated as a job name — `gmlw <job>` is shorthand for `gmlw start <job>`. Kept in
# sync with build_parser by a test.
_COMMANDS = frozenset(
    {"start", "jobs", "sessions", "export", "statusline", "workflow", "persona", "creds"}
)


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


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="gmlw",
        description=banner(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

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

    jobs = sub.add_parser("jobs", help="list the jobs with recorded activity")
    _add_json_flag(jobs)

    sessions = sub.add_parser("sessions", help="list a job's sessions")
    sessions.add_argument("job", help="the job identifier")
    _add_json_flag(sessions)

    export = sub.add_parser("export", help="report a job's recorded usage")
    export.add_argument("job", help="the job identifier")
    _add_json_flag(export)

    sub.add_parser("statusline", help="render the status line (called by the client)")

    workflow = sub.add_parser("workflow", help="author/list workflows")
    workflow_sub = workflow.add_subparsers(dest="workflow_command", metavar="<action>")
    new = workflow_sub.add_parser("new", help="author a new workflow (no job)")
    new.add_argument("name", help="the new workflow's name")
    new.add_argument(
        "--client",
        default=None,
        help="which client to wrap (default: the configured default, or claude)",
    )
    workflow_list = workflow_sub.add_parser("list", help="list the runnable workflows")
    _add_json_flag(workflow_list)

    persona = sub.add_parser("persona", help="list the selectable personas")
    persona_sub = persona.add_subparsers(dest="persona_command", metavar="<action>")
    persona_list = persona_sub.add_parser("list", help="list the selectable personas")
    _add_json_flag(persona_list)

    creds = sub.add_parser("creds", help="manage per-workflow credentials")
    creds_sub = creds.add_subparsers(dest="creds_command", metavar="<action>")
    creds_set = creds_sub.add_parser("set", help="store a workflow credential")
    creds_set.add_argument("workflow", help="the workflow the credential belongs to")
    creds_set.add_argument("name", help="the environment-variable name to export at launch")
    return parser


def format_jobs(summaries: list[JobSummary]) -> str:
    """Render the job summaries as human-readable lines.

    Args:
        summaries: The job summaries to render.

    Returns:
        The text to print (no trailing newline).
    """
    if not summaries:
        return "No jobs yet. Start one with: gmlw start <job>"
    lines = [f"{len(summaries)} job(s):", ""]
    width = max(len(summary.job) for summary in summaries)
    lines += [
        f"  {summary.job:<{width}}  {summary.session_count} session(s)" for summary in summaries
    ]
    return "\n".join(lines)


def format_sessions(job: str, sessions: list[SessionSummary]) -> str:
    """Render a job's sessions as human-readable lines.

    Args:
        job: The job the sessions belong to.
        sessions: The session summaries to render.

    Returns:
        The text to print (no trailing newline).
    """
    if not sessions:
        return f"No sessions for {job!r}. Start one with: gmlw start {job}"
    lines = [f"{job} — {len(sessions)} session(s):", ""]
    width = max(len(session.session_id) for session in sessions)
    lines += [f"  {session.session_id:<{width}}  {session.client}" for session in sessions]
    return "\n".join(lines)


def format_usage(report: UsageReport) -> str:
    """Render a job's usage report: per-turn rows, totals by model, cost, and totals.

    Args:
        report: The usage report to render.

    Returns:
        The text to print (no trailing newline).
    """
    if report.turn_count == 0 and not report.session_costs:
        return f"No usage recorded for {report.job!r} yet."
    width = max(
        (len(model.model) for model in report.models),
        default=len(_UNKNOWN_LABEL),
    )
    lines = [f"{report.job} — usage  ({report.turn_count} turn(s))", ""]
    for turn in report.turns:
        lines.append(
            f"  {_clock(turn.timestamp)}  {turn.model:<{width}}  {turn.duration_s:>5.1f}s"
            f"{_tokens(turn.input_tokens, turn.output_tokens, turn.cache_tokens)}"
            f"  · [{turn.turn_id or '-'}]"
        )
    if report.models:
        lines += ["", "  ── totals by model ──"]
        lines += [
            f"  {model.model:<{width}}  {model.calls:>3} call(s)"
            f"{_tokens(model.input_tokens, model.output_tokens, model.cache_tokens)}"
            f"  {model.duration_s:.1f}s"
            for model in report.models
        ]
    if report.session_costs:
        lines += ["", "  ── cost by session ──"]
        lines += [f"  {cost.session_id}  ${cost.cost_usd:.2f}" for cost in report.session_costs]
    lines += [
        "",
        f"  ── total ──  {report.turn_count} turn(s)"
        f"{_tokens(report.input_tokens, report.output_tokens, report.cache_tokens)}"
        f"  {report.duration_s:.1f}s  ${report.total_usd:.2f}",
    ]
    return "\n".join(lines)


_UNKNOWN_LABEL = "(unknown)"


def _clock(timestamp: float) -> str:
    """Render an epoch timestamp as a local ``HH:MM:SS``, or a dash when unset."""
    if timestamp <= 0:
        return "--:--:--"
    return datetime.fromtimestamp(timestamp, tz=UTC).astimezone().strftime("%H:%M:%S")


def _tokens(input_tokens: int, output_tokens: int, cache_tokens: int) -> str:
    """Render a token triple as ``  <in>(+<cache> cache)+<out> tok`` for the report."""
    cache = f"(+{cache_tokens} cache)" if cache_tokens else ""
    return f"  {input_tokens}{cache}+{output_tokens} tok"


def format_workflows(names: list[str]) -> str:
    """Render the runnable workflow names as human-readable lines.

    Args:
        names: The workflow names to render.

    Returns:
        The text to print (no trailing newline).
    """
    if not names:
        return "No workflows yet. Author one with: gmlw workflow new <name>"
    lines = [f"{len(names)} workflow(s):", ""]
    lines += [f"  {name}" for name in names]
    return "\n".join(lines)


def format_personas(personas: list[Persona]) -> str:
    """Render the selectable personas as human-readable lines.

    Args:
        personas: The personas to render.

    Returns:
        The text to print (no trailing newline).
    """
    if not personas:
        return "No personas."
    lines = [f'{len(personas)} persona(s)  (select with: [companion] persona = "<name>")', ""]
    width = max(len(persona.name) for persona in personas)
    lines += [f"  {persona.name:<{width}}  {persona.description}" for persona in personas]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0911  (a per-command dispatcher)
    """Run the CLI.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    resolved = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(_implicit_start(resolved))
    configure_logging(os.environ.get("GMLW_LOG_LEVEL") or config.log_level())
    # Self-initialize on a real command; skip the statusline hot path and bare help.
    if args.command not in (None, "statusline"):
        if config.config_exists():
            build_bootstrap().execute()
        else:  # first run: detect clients, seed a config with a default baked in
            _announce_first_run(build_first_run_init().execute())
    try:
        if args.command == "start":
            return _start(args)
        if args.command == "statusline":
            return _statusline()
        if args.command == "workflow":
            return _workflow(args)
        if args.command == "persona":
            return _persona(args)
        if args.command == "creds":
            return _creds(args)
        view = _view(args)  # the print-and-exit-0 commands (jobs, sessions, export)
    except (
        IdentifierError,
        SettingsUnreadableError,
        CredentialsUnreadableError,
        SpecLoadError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if view is None:
        parser.print_help()
    else:
        print(view)
    return 0


def _announce_first_run(outcome: FirstRunOutcome) -> None:
    """Narrate first-run init to stderr (stdout stays clean for view/--json output).

    Args:
        outcome: What first-run init found and chose.
    """
    if outcome.chosen is not None:
        print(
            f"gmlw: first run — set '{outcome.chosen}' as your default client. "
            "Change it any time in ~/.gmlw/config.toml.",
            file=sys.stderr,
        )
    elif not outcome.found:
        print(
            "gmlw: first run — no supported client found on your PATH "
            "(claude, cursor-agent, codex, vibe). Seeded ~/.gmlw/config.toml; "
            "install one or set [client] default there.",
            file=sys.stderr,
        )
    if outcome.persona is not None:
        print(
            f"gmlw: persona '{outcome.persona}' selected — it will greet you at launch.",
            file=sys.stderr,
        )
    # Several found but none chosen (non-interactive): stay silent; the built-in
    # 'claude' default applies and the seeded config records nothing to undo.


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
    return None


def _client(raw: str | None) -> str:
    """Resolve the client to wrap: the explicit ``--client``, else the config default."""
    return raw if raw else config.default_client()


def format_client_guidance(readiness: ClientReadiness) -> str:
    """Render install/login guidance for a client that cannot launch.

    Args:
        readiness: The not-ready verdict from the client check.

    Returns:
        The guidance text to print (no trailing newline).
    """
    if readiness.missing is not None:
        info = readiness.missing
        lines = [
            f"gmlw: client {readiness.client!r} ({info.display}) isn't on your PATH yet.",
            f"  install:     {info.install}",
            f"  then log in: {info.login}",
        ]
        others = [name for name in readiness.installed if name != readiness.client]
        if others:
            lines.append(f"  or use one you already have:  --client {others[0]}")
    else:
        supported = ", ".join(info.name for info in client_catalog.SUPPORTED)
        lines = [f"gmlw: {readiness.client!r} is not a supported client. Supported: {supported}."]
    if not readiness.installed:
        lines += ["", "No supported client is installed yet — any of these works:"]
        width = max(len(info.name) for info in client_catalog.SUPPORTED)
        for info in client_catalog.SUPPORTED:
            lines.append(f"  {info.name:<{width}}  {info.install}")
        lines.append("...then log in (see each tool's docs) before running gmlw again.")
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
        print(
            "gmlw: your current directory no longer exists (it was moved or deleted).\n"
            "  cd to a directory that exists — e.g. `cd ~` — and try again.",
            file=sys.stderr,
        )
        return False
    return True


_MAX_STATUSLINE_BYTES = 1_000_000  # a client's status payload is small JSON; cap the read


def _statusline() -> int:
    payload = "" if sys.stdin.isatty() else sys.stdin.read(_MAX_STATUSLINE_BYTES)
    # The launching caller exports GMLW_CLIENT so the status line parses with the
    # right client's parser (claude's quota vs cursor's plan block).
    line = build_render_statusline(os.environ.get("GMLW_CLIENT")).execute(
        payload,
        os.environ.get("GMLW_JOB"),
        os.environ.get("GMLW_SESSION"),
    )
    print(line)
    return 0


_START_NEEDS_JOB = (
    "gmlw: start needs a job to work on.\n"
    "  gmlw <job>          start (or resume) a session on <job>\n"
    "  gmlw start <job>    the same, spelled out\n"
    "A job groups related sessions; list yours with:  gmlw jobs"
)


def _start(args: argparse.Namespace) -> int:
    if args.job is None:  # `gmlw start` with no job — guide instead of an argparse dump
        print(_START_NEEDS_JOB, file=sys.stderr)
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
    # The free host greeting (when a companion persona is set), to stderr so it stays
    # out of any piped stdout — printed before the client takes over the terminal.
    greeting = build_render_greeting().execute()
    if greeting:
        print(greeting, file=sys.stderr)
    try:
        return build_start_job().execute(command)
    except (UnknownWorkflowError, ResumeNotSupportedError) as error:
        print(f"error: {error}")
        return 2


def _read_secret() -> str:
    """Read a secret value: a secure prompt at a TTY, else one line from stdin."""
    if sys.stdin.isatty():
        return getpass.getpass("value: ")
    return sys.stdin.readline().rstrip("\n")


def _creds(args: argparse.Namespace) -> int:
    if args.creds_command == "set":
        workflow = WorkflowName(args.workflow)
        name = EnvVarName(args.name)
        build_set_credential().execute(
            SetCredentialCommand(workflow=workflow, name=name, value=_read_secret())
        )
        print(f"stored {workflow}.{name}")
        return 0
    return 0


def _workflow(args: argparse.Namespace) -> int:
    if args.workflow_command == "new":
        client = _client(args.client)
        if not _preflight_client(client):  # client not installed — guide, don't launch
            return 2
        try:
            return build_new_workflow().execute(
                NewWorkflowCommand(name=str(args.name), client=client)
            )
        except (WorkflowNameError, WorkflowExistsError) as error:
            print(f"error: {error}")
            return 2
    if args.workflow_command == "list":
        names = build_list_workflows().execute()
        print(_as_json(names) if bool(args.json) else format_workflows(names))
        return 0
    return 0


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
