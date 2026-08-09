# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.common.action import (
    create_workflow,
    edit_workflow,
    run_init,
    run_workflow,
)
from generic_ml_wrapper.adapter.inbound.common.announcer import print_exit_receipt
from generic_ml_wrapper.adapter.inbound.common.i18n.language_change_interceptor import (
    LanguageChangeInterceptor,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
    get_active,
    get_message,
)
from generic_ml_wrapper.adapter.inbound.common.launcher import (
    preflight_client,
    preflight_cwd,
    preflight_resume_cwd,
)
from generic_ml_wrapper.adapter.inbound.common.renderer import (
    format_client_version,
    format_job_footprints,
    format_session_footprints,
    format_session_usage,
    format_set_outcome,
    format_setting_value,
    format_token_counts,
    render_error,
)
from generic_ml_wrapper.application.domain.model.archive_unreadable_error import (
    ArchiveUnreadableError,
)
from generic_ml_wrapper.application.domain.model.environment_code_already_exists_error import (
    EnvironmentCodeAlreadyExistsError,
)
from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.invalid_setting_value_error import (
    InvalidSettingValueError,
)
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.no_such_job_error import NoSuchJobError
from generic_ml_wrapper.application.domain.model.no_such_session_error import NoSuchSessionError
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
from generic_ml_wrapper.application.domain.model.workflow_name import WorkflowName
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError
from generic_ml_wrapper.application.domain.model.workflow_not_found_error import (
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.add_environment_command import (
    AddEnvironmentCommand,
)
from generic_ml_wrapper.application.port.inbound.add_role_command import AddRoleCommand
from generic_ml_wrapper.application.port.inbound.create_job_command import CreateJobCommand
from generic_ml_wrapper.application.port.inbound.export_usage_query import ExportUsageQuery
from generic_ml_wrapper.application.port.inbound.find_job_query import FindJobQuery
from generic_ml_wrapper.application.port.inbound.import_outcome import ImportOutcome
from generic_ml_wrapper.application.port.inbound.list_jobs_query import ListJobsQuery
from generic_ml_wrapper.application.port.inbound.resume_session_command import ResumeSessionCommand
from generic_ml_wrapper.application.port.inbound.set_default_environment_command import (
    SetDefaultEnvironmentCommand,
)
from generic_ml_wrapper.application.port.inbound.set_default_role_command import (
    SetDefaultRoleCommand,
)
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult
from generic_ml_wrapper.application.port.inbound.start_new_session_command import (
    StartNewSessionCommand,
)
from generic_ml_wrapper.application.wiring.composition import (
    build_add_environment,
    build_add_role,
    build_application_settings,
    build_config_commands,
    build_create_job,
    build_delete_jobs,
    build_delete_sessions,
    build_export_usage,
    build_export_usage_to_file,
    build_export_workflow,
    build_find_job,
    build_import_workflow,
    build_list_clients,
    build_list_environments,
    build_list_jobs,
    build_list_launch_clients,
    build_list_personas,
    build_list_roles,
    build_list_rules,
    build_list_sessions,
    build_list_workflow_catalog,
    build_resume_session_for_job,
    build_set_default_environment,
    build_set_default_role,
    build_start_new_session_for_job,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.tui.menu_app import MenuChoice

CLIENT_DEFAULT_KEY = "client.default"


def tui_main() -> int:
    """Run the interactive menu until something ends the session.

    Two kinds of thing come back out of the menu, and the difference is this loop. A
    *launch* (start, resume, run, authoring) gives the terminal to a client and gmlw is
    done when that client is. Everything else -- exporting, importing, deleting, re-running
    setup -- is an errand: it needs the restored terminal to ask a question or print a
    result, and then the user is still in the middle of using the menu. Those return here
    and the menu is rebuilt, which is also what refreshes the job list a delete just changed.

    Returns:
        The process exit code.
    """
    if build_application_settings().setup_needed():  # first run — setup wins over the menu
        setup_exit_code = run_init()
        if setup_exit_code != 0:
            return setup_exit_code
    while True:
        choice = _run_menu()
        if choice is None:  # quit from the menu itself
            return 0
        if choice.action == "reload-for-language":
            continue  # nothing was printed to read: rebuild straight into the new language
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
    print(get_message("tui.return"), file=sys.stderr)
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
    from generic_ml_wrapper.adapter.inbound.tui.menu_app import (  # noqa: PLC0415
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
            JobChoice(job=s.job, session_count=s.session_count)
            for s in build_list_jobs().execute(ListJobsQuery())
        ]

    def _preview_jobs(selected: tuple[str, ...]) -> str:
        try:
            return format_job_footprints(build_delete_jobs().preview(list(selected)))
        except NoSuchJobError as error:  # the list went stale under us
            return render_error(error)

    def _delete_jobs_in_app(selected: tuple[str, ...]) -> str:
        try:
            outcome = build_delete_jobs().execute(list(selected))
        except NoSuchJobError as error:
            return render_error(error)
        kept = [footprint for footprint in outcome if not footprint.removed]
        if not kept:
            return get_message("delete.jobs.done", count=len(outcome))
        return get_message(
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
            return render_error(error)

    def _delete_sessions_in_app(job: str, selected: tuple[str, ...]) -> str:
        try:
            outcome = build_delete_sessions().execute(job, list(selected))
        except (NoSuchJobError, NoSuchSessionError) as error:
            return render_error(error)
        kept = [footprint for footprint in outcome if not footprint.removed]
        if not kept:
            return get_message("delete.sessions.done", count=len(outcome), job=job)
        return get_message(
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
            return get_message(
                "workflow.export.written", path=build_export_workflow().execute(name)
            )
        except (WorkflowNameError, WorkflowNotFoundError) as error:
            return f"✗ {render_error(error)}"

    def _install_in_app(archive: str, replace: bool) -> ImportAttempt:
        try:
            result = build_import_workflow().execute(archive, replace=replace)
        except (ArchiveUnreadableError, WorkflowNameError) as error:
            return ImportAttempt(f"✗ {render_error(error)}")
        if result.outcome is ImportOutcome.REFUSED:
            # Not an error: the use case reports the clash instead of resolving it, so the
            # question can be asked. The menu turns this into a confirmation screen.
            return ImportAttempt(
                get_message("workflow.import.exists", name=result.name), needs_confirmation=True
            )
        if result.outcome is ImportOutcome.REPLACED:
            return ImportAttempt(
                get_message("workflow.import.replaced", name=result.name, backup=result.backup)
            )
        return ImportAttempt(get_message("workflow.import.done", name=result.name))

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
        report = build_export_usage().execute(ExportUsageQuery(job=str(JobId(job))))
        message_source = get_active()
        if report.turn_count == 0 and not report.session_costs:
            return UsageView(
                job=job,
                empty=True,
                summary=message_source.get_message("usage.none", job=repr(job)),
                model_rows=(),
                session_rows=(),
            )
        summary = message_source.get_message(
            "usage.total",
            count=report.turn_count,
            tokens=format_token_counts(
                report.input_tokens, report.output_tokens, report.cache_tokens, message_source
            ),
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

    def _save_usage(job: str) -> str:  # writes the full JSON report; returns where it went
        return build_export_usage_to_file().execute(ExportUsageQuery(job=str(JobId(job))))

    def _clients() -> list[ClientRow]:  # runs on a worker thread: version reads are subprocesses
        return [
            ClientRow(
                client=status.display,
                version=format_client_version(status, message_source),
                resumable=message_source.get_message("clients.yes")
                if status.resumable
                else message_source.get_message("clients.no"),
                default=message_source.get_message("clients.default_marker")
                if status.is_default
                else "",
                name=status.name,  # not shown: the id written when the row is made the default
                note=(  # the caveat on the resume cell, kept out of the column
                    f"{message_source.get_message('clients.col.resumable')}: "
                    f"{message_source.get_message(status.resume_hint)}"
                    if status.resume_hint
                    else ""
                ),
            )
            for status in build_list_clients().execute()
        ]

    # The config switchers (browsers that mutate config in place, no hand-off): each fetches
    # its options + current value and injects an ``apply`` setter and, for the folder-backed
    # ones, a ``create``. The app stays pure -- the wiring owns every outbound call.
    config_commands = build_config_commands()

    message_source = get_active()

    def _switcher(
        label_key: str,
        key: str,
        choices: list[SwitchChoice],
        create: Callable[[str], CreateOutcome] | None = None,
    ) -> Switcher:
        current = config_commands.get(key).value
        crumb = (
            f"gmlw > {message_source.get_message('tui.config')} > "
            f"{message_source.get_message(label_key)}"
        )

        def apply(value: str) -> str:  # localised confirmation, shown in the detail panel
            changed = config_commands.set(key, value).changed
            return message_source.get_message(
                "tui.switch.set" if changed else "tui.switch.unchanged", value=value
            )

        return Switcher(
            key=key,
            crumb=crumb,
            choices=choices,
            current=current if isinstance(current, str) else None,
            apply=apply,
            create=create,
        )

    def _create_role(label: str) -> CreateOutcome:
        try:  # add + make it the default, so "New" from the switcher also switches
            result = build_add_role().execute(AddRoleCommand(label=label))
        except UncodableRoleLabelError:
            return CreateOutcome(None, message_source.get_message("tui.create.bad"))
        except RoleCodeAlreadyExistsError:
            return CreateOutcome(None, message_source.get_message("tui.create.exists"))
        build_set_default_role().execute(SetDefaultRoleCommand(code=result.role.code))
        return CreateOutcome(SwitchChoice(result.role.code, result.role.label, ""), "")

    def _create_environment(label: str) -> CreateOutcome:
        try:  # add + make it the default, so "New" from the switcher also switches
            result = build_add_environment().execute(AddEnvironmentCommand(label=label))
        except UncodableEnvironmentLabelError:
            return CreateOutcome(None, message_source.get_message("tui.create.bad"))
        except EnvironmentCodeAlreadyExistsError:
            return CreateOutcome(None, message_source.get_message("tui.create.exists"))
        build_set_default_environment().execute(
            SetDefaultEnvironmentCommand(code=result.environment.code)
        )
        return CreateOutcome(
            SwitchChoice(result.environment.code, result.environment.label, ""), ""
        )

    personas = [
        SwitchChoice(p.name, p.name, p.description) for p in build_list_personas().execute()
    ]
    environments = [
        SwitchChoice(e.code, e.label, e.description) for e in build_list_environments().execute()
    ]
    roles = [SwitchChoice(r.code, r.label, r.description) for r in build_list_roles().execute()]

    switchers: dict[str, Switcher] = {}
    if personas:
        switchers["persona"] = _switcher("tui.cfg.persona", "companion.persona", personas)
    switchers["environment"] = _switcher(
        "tui.cfg.environment", "profile.default_environment", environments, _create_environment
    )
    switchers["role"] = _switcher("tui.cfg.role", "profile.default_role", roles, _create_role)

    # Config Get/Set: the settings snapshot + a setter, injected like the switchers. The picker
    # reads the snapshot; a set goes through the same ConfigCommandsUseCase.set that
    # the CLI's `config set` uses
    # uses (values/defaults pre-rendered through setting_value so the app stays format-free).
    message_source = get_active()

    dedicated_menu_keys = {switcher.key for switcher in switchers.values()} | {CLIENT_DEFAULT_KEY}

    def _config_settings() -> list[ConfigSetting]:
        return [
            ConfigSetting(
                key=view.key,
                value=format_setting_value(view.value, message_source),
                default=format_setting_value(view.default, message_source),
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
        except InvalidSettingValueError as error:
            return ConfigSetResult(ok=False, message=render_error(error))
        language_changed = LanguageChangeInterceptor.after_setting_written(key, raw)
        return ConfigSetResult(
            ok=True,
            message=format_set_outcome(outcome),
            value=format_setting_value(outcome.new, message_source),
            language_changed=language_changed,
        )

    def _set_default_client(name: str) -> ConfigSetResult:  # Config → Clients: pick the default
        return _apply_setting(CLIENT_DEFAULT_KEY, name)

    config_catalog = ConfigCatalog(
        crumb=f"gmlw > {message_source.get_message('tui.config')}",
        settings=_config_settings(),
        apply=_apply_setting,
    )

    def _validate_job(name: str) -> str | None:  # in-form validation before any teardown
        try:
            JobId(name)
        except IdentifierError:
            return message_source.get_message("tui.newjob.invalid")
        return None

    def _validate_workflow(name: str) -> str | None:  # empty is fine — named at the end
        if not name:
            return None
        try:
            WorkflowName(name)
        except IdentifierError:
            return message_source.get_message("tui.wf.invalid")
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
        current_client=build_application_settings().resolve_client(None),
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
    client = choice.client or build_application_settings().resolve_client(None)
    # -- the one errand: done on the terminal, then back to the menu -------------------- #
    if choice.action == "init":
        # Config → Setup genuinely needs the terminal: it is an interview, and it can
        # install a client. Everything else the menu does that writes -- deleting,
        # exporting, importing -- stays in the app, so the user keeps their place.
        run_init()
        return None
    # -- launches: the terminal goes to a client, and gmlw ends with it ----------------- #
    if choice.action == "run" and choice.workflow is not None:  # launch on the chosen workflow
        return run_workflow(choice.workflow, client)
    if choice.action == "workflow_new":  # author a new workflow (name may be None -> proposed)
        return create_workflow(choice.workflow, client, choice.guided)
    if choice.action == "workflow_edit" and choice.workflow is not None:
        return edit_workflow(choice.workflow, client, choice.guided)
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
    # Guard the folder the launch will actually use: a resumed session's stored folder, or
    # the current directory for a new start (or a pre-folder resume, whose cwd is ``None``).
    if picked_cwd is not None:
        if not preflight_resume_cwd(picked_cwd):
            return 2
    elif not preflight_cwd():
        return 2
    if not resume and not preflight_client(client):  # a new session needs the client installed
        return 2
    try:
        result = _launch_for_the_menu(job, resume, session, client)
    except (NoSuchJobError, NoSuchSessionError, ResumeNotSupportedError) as error:
        print(render_error(error), file=sys.stderr)
        return 2
    print_exit_receipt(result)
    return result.exit_code


def _launch_for_the_menu(
    job: str, resume: bool, session: str | None, client: str
) -> StartJobResult:
    """Run what the menu picked: a specific session, the latest, or a fresh one.

    Args:
        job: The job to launch.
        resume: Whether this reopens an existing session.
        session: The session id the picker chose, or ``None`` for the latest.
        client: The resolved client, used only when starting fresh.

    Returns:
        The run's outcome.

    Raises:
        NoSuchJobError: When the job is gone since the menu listed it.
        NoSuchSessionError: When the picked session is gone, or the job has never run.
    """
    if not resume:
        build_create_job().execute(CreateJobCommand(job=job))
        return build_start_new_session_for_job().execute(
            StartNewSessionCommand(job=job, client=client)
        )
    found = build_find_job().execute(FindJobQuery(job=job))
    picked = found.session_for(session) if session is not None else found.latest_session()
    return build_resume_session_for_job().execute(ResumeSessionCommand(session=picked))
