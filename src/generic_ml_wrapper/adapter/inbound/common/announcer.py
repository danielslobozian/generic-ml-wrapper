# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.cli.hints import next_hint
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.migration_report import MigrationReport
from generic_ml_wrapper.application.domain.model.slug_migration_report import SlugMigrationReport
from generic_ml_wrapper.application.port.inbound.create_workflow_result import CreateWorkflowResult
from generic_ml_wrapper.application.port.inbound.export_usage_query import ExportUsageQuery
from generic_ml_wrapper.application.port.inbound.init_outcome import InitOutcome
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult
from generic_ml_wrapper.application.port.inbound.workflow_outcome import WorkflowOutcome
from generic_ml_wrapper.application.wiring import localization as i18n
from generic_ml_wrapper.application.wiring.composition import (
    build_check_for_update,
    build_export_usage,
)
from generic_ml_wrapper.application.wiring.diagnostics_log import log


def announce_init(outcome: InitOutcome) -> None:
    """Narrate the init pass to stderr (stdout stays clean for view/--json output)."""
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
                role_code=outcome.role.code,
                environment=outcome.environment.label,
                environment_code=outcome.environment.code,
            ),
            file=sys.stderr,
        )
    else:  # legacy install: the answers were merged into the existing config
        print(loc.t("init.announce.legacy"), file=sys.stderr)
        for change in outcome.overwrites:
            print(loc.t("init.announce.updated", change=change), file=sys.stderr)
    if outcome.client is not None:
        print(loc.t("init.announce.client", client=outcome.client), file=sys.stderr)
    elif not outcome.found:
        print(loc.t("init.announce.no_client"), file=sys.stderr)
    if outcome.persona is not None:
        print(loc.t("init.announce.persona", persona=outcome.persona), file=sys.stderr)


def announce_migration(report: MigrationReport) -> None:
    """Narrate a layout migration to stderr, only when it actually moved or skipped."""
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


def announce_create_workflow(result: CreateWorkflowResult) -> None:
    """Report to stderr how an authoring session's draft resolved.

    One of three outcomes: deployed, blocked by a name collision, or left incomplete with
    the draft kept.
    """
    if result.outcome is WorkflowOutcome.DEPLOYED:
        print(i18n.t("workflow.new.deployed", name=result.name), file=sys.stderr)
    elif result.outcome is WorkflowOutcome.COLLISION:
        print(
            i18n.t("workflow.new.collision", name=result.name, draft=result.draft_path),
            file=sys.stderr,
        )
    else:  # INCOMPLETE — no finished marker; the draft is kept so nothing is lost
        print(i18n.t("workflow.new.incomplete", draft=result.draft_path), file=sys.stderr)


def announce_slug_migration(report: SlugMigrationReport) -> None:
    """Narrate the slug migration to stderr, only when it renamed something."""
    if not report.did_anything:
        return
    loc = i18n.active()
    items = ", ".join(f"{old} → {new}" for old, new in report.renamed)
    print(loc.t("migration.slugs", count=len(report.renamed), items=items), file=sys.stderr)


def print_exit_receipt(result: StartJobResult) -> None:
    """Print the exit receipt to stderr: this session's and the job's cost, then next steps.

    A persistent summary on the return (the client has exited): the cost of the session and
    the job, the resume/report commands, and one usage-driven, suppressible tip. Best-effort
    — the cost line degrades to just the commands if the usage read fails, never raising on
    the way out.
    """
    loc = i18n.active()
    try:
        report = build_export_usage().execute(ExportUsageQuery(job=str(JobId(result.job))))
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
        log.debug(f"exit receipt usage read failed: {error}")
    print(loc.t("receipt.resume", job=result.job), file=sys.stderr)
    print(loc.t("receipt.report", job=result.job), file=sys.stderr)
    latest = build_check_for_update().execute()
    if latest:
        print(loc.t("receipt.update", latest=latest, current=__version__), file=sys.stderr)
    tip = next_hint(loc)
    if tip:
        print(tip, file=sys.stderr)
