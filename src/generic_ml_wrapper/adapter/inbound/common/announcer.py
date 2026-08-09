# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.cli.hints import next_hint
from generic_ml_wrapper.adapter.inbound.common.i18n.language_context_holder import (
    LanguageContextHolder,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
    get_active,
    get_message,
)
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.migration_report import MigrationReport
from generic_ml_wrapper.application.domain.model.slug_migration_report import SlugMigrationReport
from generic_ml_wrapper.application.port.inbound.create_workflow_result import CreateWorkflowResult
from generic_ml_wrapper.application.port.inbound.export_usage_query import ExportUsageQuery
from generic_ml_wrapper.application.port.inbound.init_outcome import InitOutcome
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult
from generic_ml_wrapper.application.port.inbound.workflow_outcome import WorkflowOutcome
from generic_ml_wrapper.application.wiring.composition import (
    build_check_for_update,
    build_export_usage,
)
from generic_ml_wrapper.application.wiring.diagnostics_log import log


def print_init(outcome: InitOutcome) -> None:
    """Narrate the init pass to stderr (stdout stays clean for view/--json output)."""
    # set_active ran at startup off $LANG (config had no language yet). Now that init has
    # chosen one, re-seed the global active so this narration -- and every user string after
    # init in this process -- speaks the chosen language, not the OS locale.
    LanguageContextHolder.set_language(outcome.language)
    message_source = get_active()
    if outcome.fresh:
        print(
            message_source.get_message(
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
        print(message_source.get_message("init.announce.legacy"), file=sys.stderr)
        for change in outcome.overwrites:
            print(
                message_source.get_message("init.announce.updated", change=change), file=sys.stderr
            )
    if outcome.client is not None:
        print(
            message_source.get_message("init.announce.client", client=outcome.client),
            file=sys.stderr,
        )
    elif not outcome.found:
        print(message_source.get_message("init.announce.no_client"), file=sys.stderr)
    if outcome.persona is not None:
        print(
            message_source.get_message("init.announce.persona", persona=outcome.persona),
            file=sys.stderr,
        )


def print_migration(report: MigrationReport) -> None:
    if not report.did_anything:
        return
    message_source = get_active()
    if report.moved:
        print(
            message_source.get_message(
                "migration.moved",
                count=len(report.moved),
                environment=report.environment,
                items=", ".join(report.moved),
            ),
            file=sys.stderr,
        )
    if report.skipped:  # a same-named entry already existed at the target — never overwritten
        print(
            message_source.get_message(
                "migration.skipped",
                count=len(report.skipped),
                environment=report.environment,
                items=", ".join(report.skipped),
            ),
            file=sys.stderr,
        )


def print_create_workflow(result: CreateWorkflowResult) -> None:
    """Report to stderr how an authoring session's draft resolved.

    One of three outcomes: deployed, blocked by a name collision, or left incomplete with
    the draft kept.
    """
    if result.outcome is WorkflowOutcome.DEPLOYED:
        print(get_message("workflow.new.deployed", name=result.name), file=sys.stderr)
    elif result.outcome is WorkflowOutcome.COLLISION:
        print(
            get_message("workflow.new.collision", name=result.name, draft=result.draft_path),
            file=sys.stderr,
        )
    else:  # INCOMPLETE — no finished marker; the draft is kept so nothing is lost
        print(get_message("workflow.new.incomplete", draft=result.draft_path), file=sys.stderr)


def print_slug_migration(report: SlugMigrationReport) -> None:
    if not report.did_anything:
        return
    message_source = get_active()
    items = ", ".join(f"{old} → {new}" for old, new in report.renamed)
    print(
        message_source.get_message("migration.slugs", count=len(report.renamed), items=items),
        file=sys.stderr,
    )


def print_exit_receipt(result: StartJobResult) -> None:
    """Print the exit receipt to stderr: this session's and the job's cost, then next steps.

    Best-effort — the cost line degrades to just the commands if the usage read fails,
    never raising on the way out.
    """
    message_source = get_active()
    try:
        report = build_export_usage().execute(ExportUsageQuery(job=str(JobId(result.job))))
        session_cost = next(
            (c.cost_usd for c in report.session_costs if c.session_id == result.session_id),
            0.0,
        )
        print(
            message_source.get_message(
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
    print(message_source.get_message("receipt.resume", job=result.job), file=sys.stderr)
    print(message_source.get_message("receipt.report", job=result.job), file=sys.stderr)
    latest = build_check_for_update().execute()
    if latest:
        print(
            message_source.get_message("receipt.update", latest=latest, current=__version__),
            file=sys.stderr,
        )
    tip = next_hint(message_source)
    if tip:
        print(tip, file=sys.stderr)
