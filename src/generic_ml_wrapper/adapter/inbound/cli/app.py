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
from generic_ml_wrapper.application.domain.model.identifiers import (
    EnvVarName,
    IdentifierError,
    JobId,
    WorkflowName,
)
from generic_ml_wrapper.application.port.inbound.export_usage import UsageReport
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
    build_export_usage,
    build_list_jobs,
    build_list_sessions,
    build_list_workflows,
    build_new_workflow,
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
    start.add_argument("job", help="the job identifier")
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


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(os.environ.get("GMLW_LOG_LEVEL") or config.log_level())
    # Self-initialize on a real command; skip the statusline hot path and bare help.
    if args.command not in (None, "statusline"):
        build_bootstrap().execute()
    try:
        if args.command == "start":
            return _start(args)
        if args.command == "statusline":
            return _statusline()
        if args.command == "workflow":
            return _workflow(args)
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


_MAX_STATUSLINE_BYTES = 1_000_000  # a client's status payload is small JSON; cap the read


def _statusline() -> int:
    payload = "" if sys.stdin.isatty() else sys.stdin.read(_MAX_STATUSLINE_BYTES)
    line = build_render_statusline().execute(
        payload,
        os.environ.get("GMLW_JOB"),
        os.environ.get("GMLW_SESSION"),
    )
    print(line)
    return 0


def _start(args: argparse.Namespace) -> int:
    workflow = None if args.workflow is None else str(args.workflow)
    command = StartJobCommand(
        job=JobId(args.job),
        client=_client(args.client),
        resume_latest=bool(args.resume_latest),
        workflow=workflow,
    )
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
        try:
            return build_new_workflow().execute(
                NewWorkflowCommand(name=str(args.name), client=_client(args.client))
            )
        except (WorkflowNameError, WorkflowExistsError) as error:
            print(f"error: {error}")
            return 2
    if args.workflow_command == "list":
        names = build_list_workflows().execute()
        print(_as_json(names) if bool(args.json) else format_workflows(names))
        return 0
    return 0
