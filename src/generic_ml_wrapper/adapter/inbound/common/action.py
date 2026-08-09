# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys

from generic_ml_wrapper.adapter.inbound.cli.setup.interview import run_interview
from generic_ml_wrapper.adapter.inbound.common.announcer import (
    print_create_workflow,
    print_exit_receipt,
    print_init,
    print_migration,
    print_slug_migration,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.language_context_holder import (
    LanguageContextHolder,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
    get_active,
    get_message,
)
from generic_ml_wrapper.adapter.inbound.common.launcher import (
    preflight_client,
    preflight_cwd,
)
from generic_ml_wrapper.adapter.inbound.common.renderer import get_farewell, render_error
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.no_edit_to_resume_error import NoEditToResumeError
from generic_ml_wrapper.application.domain.model.resume_not_supported_error import (
    ResumeNotSupportedError,
)
from generic_ml_wrapper.application.domain.model.unknown_workflow_error import UnknownWorkflowError
from generic_ml_wrapper.application.domain.model.workflow_exists_error import WorkflowExistsError
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError
from generic_ml_wrapper.application.domain.model.workflow_not_found_error import (
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.create_job_command import CreateJobCommand
from generic_ml_wrapper.application.port.inbound.create_workflow_command import (
    CreateWorkflowCommand,
)
from generic_ml_wrapper.application.port.inbound.edit_workflow_command import EditWorkflowCommand
from generic_ml_wrapper.application.port.inbound.resume_edit_workflow_command import (
    ResumeEditWorkflowCommand,
)
from generic_ml_wrapper.application.port.inbound.start_new_session_command import (
    StartNewSessionCommand,
)
from generic_ml_wrapper.application.wiring.composition import (
    build_create_job,
    build_create_workflow,
    build_edit_workflow,
    build_list_clients,
    build_list_environment_examples,
    build_list_personas,
    build_list_role_examples,
    build_list_supported_clients,
    build_migrate_layout,
    build_migrate_slugs,
    build_resume_edit_workflow,
    build_save_init_answers,
    build_start_new_session_for_job,
    default_user_name,
    platform_name,
)


def run_init() -> int:
    answers = run_interview(
        languages=get_active().available_languages(),
        default_language=LanguageContextHolder.get_language(),
        default_name=default_user_name(),
        personas=build_list_personas().execute(),
        clients=build_list_clients().execute(),
        supported=build_list_supported_clients().execute(),
        system=platform_name(),
        role_examples=build_list_role_examples(),
        environment_examples=build_list_environment_examples(),
    )
    if answers is None:  # no client installed, or the last question declined
        return 2
    print_init(build_save_init_answers().execute(answers))
    print_migration(build_migrate_layout().execute())
    print_slug_migration(build_migrate_slugs().execute())
    print(get_message("init.reinit_hint"), file=sys.stderr)  # how to re-run setup from the menu
    return 0


def run_workflow(workflow: str, client: str, client_args: str | None = None) -> int:
    """Launch the client on a workflow's own job.

    Args:
        workflow: Doubles as the job name the sessions accumulate under.
        client: Already resolved — this is not a raw ``--client`` value.
        client_args: ``None`` uses the client's configured launch arguments rather than
            meaning "none".

    Returns:
        The client's exit code, or ``2`` when a preflight refused or the workflow is
        unknown.
    """
    if not preflight_cwd():  # deleted working directory — the client would crash on getcwd
        return 2
    if not preflight_client(client):
        return 2
    try:
        build_create_job().execute(CreateJobCommand(job=str(JobId(workflow))))
        result = build_start_new_session_for_job().execute(
            StartNewSessionCommand(
                job=str(JobId(workflow)),
                client=client,
                workflow=workflow,
                client_args=client_args,
            )
        )
    except (UnknownWorkflowError, ResumeNotSupportedError) as error:
        print(render_error(error))
        return 2
    print(get_farewell(), file=sys.stderr)
    print_exit_receipt(result)
    return result.exit_code


def create_workflow(label: str | None, client: str, guided: bool, *, description: str = "") -> int:
    """Author a new workflow through an editing session on the client.

    Args:
        label: A seed only — the slug is derived from whatever the session settles on, so
            ``None`` leaves the naming to the end.
        client: Already resolved — this is not a raw ``--client`` value.
        guided: Runs the facilitative authoring experience rather than the direct one.
        description: Carried into the workflow as its longer line.

    Returns:
        The session's exit code, or ``2`` when the client cannot launch or the seed name
        is already taken.
    """
    if not preflight_client(client):
        return 2
    try:
        result = build_create_workflow().execute(
            CreateWorkflowCommand(
                label=label, client=client, guided=guided, description=description
            )
        )
    except WorkflowExistsError:
        print(get_message("workflow.new.exists", name=label), file=sys.stderr)
        return 2
    except WorkflowNameError as error:
        print(render_error(error))
        return 2
    print_create_workflow(result)
    return result.exit_code


def edit_workflow(workflow_name: str, client: str, guided: bool) -> int:
    """Open a workflow for editing on the client.

    Args:
        workflow_name: The slug, as ``gmlw run`` takes it.
        client: Already resolved — this is not a raw ``--client`` value.
        guided: Runs the facilitative authoring experience rather than the direct one.

    Returns:
        The session's exit code, or ``2`` when the client cannot launch or the workflow
        is unknown.
    """
    if not preflight_client(client):
        return 2
    try:
        return build_edit_workflow().execute(
            EditWorkflowCommand(name=workflow_name, client=client, guided=guided)
        )
    except (WorkflowNameError, WorkflowNotFoundError) as error:
        print(render_error(error))
        return 2


def resume_edit_workflow(workflow_name: str) -> int:
    """Pick up an interrupted edit of a workflow.

    No client is resolved and none is checked: the session being reopened carries its
    own, so probing for the configured default would guide the user towards installing
    something this run will not touch.

    Args:
        workflow_name: The workflow whose last editing session should be reopened.

    Returns:
        The session's exit code, or ``2`` when the workflow is unknown or has no edit to
        resume.
    """
    try:
        return build_resume_edit_workflow().execute(
            ResumeEditWorkflowCommand(workflow_name=workflow_name)
        )
    except NoEditToResumeError as error:
        print(
            get_message("workflow.edit.nothing_to_resume", error=render_error(error)),
            file=sys.stderr,
        )
        return 2
    except (WorkflowNameError, WorkflowNotFoundError) as error:
        print(render_error(error))
        return 2
