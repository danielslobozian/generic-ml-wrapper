# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The composition root: build the wired inbound use cases."""

from __future__ import annotations

import getpass
import os
import uuid
from datetime import datetime
from pathlib import Path

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_migrator import (
    FilesystemLayoutMigrator,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_seeder import (
    FilesystemLayoutSeeder,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_slug_migrator import (
    FilesystemSlugMigrator,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.http_client_versions import HttpClientVersions
from generic_ml_wrapper.adapter.outbound.bootstrap.path_client_detector import PathClientDetector
from generic_ml_wrapper.adapter.outbound.bootstrap.subprocess_command_runner import (
    SubprocessCommandRunner,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.system_clipboard import SystemClipboard
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_axis_chooser import TtyAxisChooser
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_client_setup import TtyClientSetup
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_guided_chooser import TtyGuidedChooser
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_language_chooser import TtyLanguageChooser
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_persona_chooser import TtyPersonaChooser
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_text_prompt import TtyTextPrompt
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_workflow_chooser import TtyWorkflowChooser
from generic_ml_wrapper.adapter.outbound.caller.default_provider import DefaultCliCallerProvider
from generic_ml_wrapper.adapter.outbound.compress.cache_backed_compressor import (
    CacheBackedContextCompressor,
)
from generic_ml_wrapper.adapter.outbound.config.tomlkit_config_writer import TomlkitConfigWriter
from generic_ml_wrapper.adapter.outbound.credentials.filesystem_credentials_store import (
    FilesystemCredentialsStore,
)
from generic_ml_wrapper.adapter.outbound.persona.filesystem_persona_source import (
    FilesystemPersonaSource,
)
from generic_ml_wrapper.adapter.outbound.plugin.filesystem_plugin_source import (
    FilesystemPluginSource,
)
from generic_ml_wrapper.adapter.outbound.status.claude_status_parser import ClaudeStatusParser
from generic_ml_wrapper.adapter.outbound.status.cursor_status_parser import CursorStatusParser
from generic_ml_wrapper.adapter.outbound.store.filesystem_transcript_store import (
    FilesystemTranscriptStore,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStore
from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_source import (
    FilesystemWorkflowSource,
)
from generic_ml_wrapper.adapter.outbound.workspace.local_workspace_inspector import (
    LocalGitWorkspaceInspector,
)
from generic_ml_wrapper.application.domain.service.hook import HookPhase
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.port.inbound.bootstrap import Bootstrap
from generic_ml_wrapper.application.port.inbound.check_client_ready import CheckClientReady
from generic_ml_wrapper.application.port.inbound.config_commands import ConfigCommands
from generic_ml_wrapper.application.port.inbound.edit_workflow import EditWorkflow
from generic_ml_wrapper.application.port.inbound.export_usage import ExportUsage
from generic_ml_wrapper.application.port.inbound.init import Init
from generic_ml_wrapper.application.port.inbound.list_jobs import ListJobs
from generic_ml_wrapper.application.port.inbound.list_personas import ListPersonas
from generic_ml_wrapper.application.port.inbound.list_plugins import ListPlugins
from generic_ml_wrapper.application.port.inbound.list_sessions import ListSessions
from generic_ml_wrapper.application.port.inbound.list_workflows import ListWorkflows
from generic_ml_wrapper.application.port.inbound.migrate_layout import MigrateLayout
from generic_ml_wrapper.application.port.inbound.migrate_slugs import MigrateSlugs
from generic_ml_wrapper.application.port.inbound.new_workflow import NewWorkflow
from generic_ml_wrapper.application.port.inbound.render_greeting import RenderGreeting
from generic_ml_wrapper.application.port.inbound.render_statusline import RenderStatusline
from generic_ml_wrapper.application.port.inbound.set_credential import SetCredential
from generic_ml_wrapper.application.port.inbound.start_job import StartJob
from generic_ml_wrapper.application.port.outbound.client_status import ClientStatusParserPort
from generic_ml_wrapper.application.port.outbound.hook import HookPort
from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort
from generic_ml_wrapper.application.usecase.bootstrap import BootstrapUseCase
from generic_ml_wrapper.application.usecase.check_client_ready import CheckClientReadyUseCase
from generic_ml_wrapper.application.usecase.edit_workflow import EditWorkflowUseCase
from generic_ml_wrapper.application.usecase.export_usage import ExportUsageUseCase
from generic_ml_wrapper.application.usecase.init import InitUseCase
from generic_ml_wrapper.application.usecase.list_jobs import ListJobsUseCase
from generic_ml_wrapper.application.usecase.list_personas import ListPersonasUseCase
from generic_ml_wrapper.application.usecase.list_plugins import ListPluginsUseCase
from generic_ml_wrapper.application.usecase.list_sessions import ListSessionsUseCase
from generic_ml_wrapper.application.usecase.list_workflows import ListWorkflowsUseCase
from generic_ml_wrapper.application.usecase.migrate_layout import MigrateLayoutUseCase
from generic_ml_wrapper.application.usecase.migrate_slugs import MigrateSlugsUseCase
from generic_ml_wrapper.application.usecase.new_workflow import NewWorkflowUseCase
from generic_ml_wrapper.application.usecase.render_greeting import RenderGreetingUseCase
from generic_ml_wrapper.application.usecase.render_statusline import RenderStatuslineUseCase
from generic_ml_wrapper.application.usecase.set_credential import SetCredentialUseCase
from generic_ml_wrapper.application.usecase.start_job import StartJobUseCase
from generic_ml_wrapper.application.usecase.update_config import UpdateConfigUseCase
from generic_ml_wrapper.common import config, paths
from generic_ml_wrapper.common.i18n import (
    SUPPORTED_LANGUAGES,
    Localizer,
    active,
    load_localizer,
    resolve_language,
)
from generic_ml_wrapper.common.spec_loader import load_class


def _ledger() -> Ledger:
    """The shared SQLite ledger backing the session/turn/usage stores."""
    return Ledger(paths.LEDGER)


def _transcript() -> TranscriptPort | None:
    """The transcript store when ``[transcript]`` is enabled, else ``None`` (off)."""
    settings = config.transcript()
    if not settings.enabled:
        return None
    root = Path(settings.root) if settings.root else paths.TRANSCRIPTS
    return FilesystemTranscriptStore(root)


def _workflow_source(interceptors: InterceptorChain) -> FilesystemWorkflowSource:
    """Build the filesystem workflow source with the standard ``~/.gmlw`` roots.

    Args:
        interceptors: The interceptor chain applied to context sections at compile.

    Returns:
        A workflow source that compiles context from workflows, profile, and rules.
    """
    return FilesystemWorkflowSource(
        paths.WORKFLOWS,
        paths.PROFILE,
        paths.RULES,
        interceptors,
        personas=build_persona_source(),
        compressor=CacheBackedContextCompressor(),
        startup=config.startup,
        companion=lambda: config.companion().persona,
        environments_root=paths.ENVIRONMENTS,
        default_environment=config.default_environment,
        default_role=config.default_role,
    )


def build_persona_source() -> FilesystemPersonaSource:
    """Build the filesystem persona source rooted at ``~/.gmlw/personas``.

    Returns:
        A persona source that seeds and reads the packaged personas.
    """
    return FilesystemPersonaSource(paths.PERSONAS)


def build_list_personas() -> ListPersonas:
    """Build the ListPersonas use case wired to the persona source.

    Returns:
        A ready-to-run ListPersonas.
    """
    return ListPersonasUseCase(build_persona_source())


def build_plugin_source() -> FilesystemPluginSource:
    """Build the filesystem plugin source rooted at ``~/.gmlw/plugins``.

    Returns:
        A plugin source that lists plugins and resolves id references.
    """
    return FilesystemPluginSource(paths.PLUGINS)


def build_list_plugins() -> ListPlugins:
    """Build the ListPlugins use case wired to the plugin source.

    Returns:
        A ready-to-run ListPlugins.
    """
    return ListPluginsUseCase(build_plugin_source())


def build_render_greeting() -> RenderGreeting:
    """Build the RenderGreeting use case wired to the persona source and live facts.

    Returns:
        A ready-to-run RenderGreeting (free, local; no metering).
    """
    return RenderGreetingUseCase(
        personas=build_persona_source(),
        companion=config.companion,
        workspace=LocalGitWorkspaceInspector(),
        clock=lambda: datetime.now().astimezone(),
        username=getpass.getuser,
    )


def _interceptor_chain() -> InterceptorChain:
    """Build the interceptor chain from ``[[interceptors]]`` config.

    A configured interceptor whose spec cannot be loaded raises ``SpecLoadError`` (the
    CLI surfaces it) rather than being silently skipped -- a config typo should not
    quietly disable an interceptor the user asked for.

    Returns:
        The configured chain (empty when none are configured).
    """
    loaded: list[tuple[str, InterceptorPort]] = []
    for target, spec in config.interceptors():
        # A configured-but-unloadable spec is a config error the user should see -- not a
        # silent no-op that disables an interceptor they asked for. load_class raises
        # SpecLoadError, which the CLI surfaces (nothing configured -> nothing loaded).
        interceptor_class = load_class(spec, InterceptorPort)
        # load_class guarantees a concrete subclass; the abstract-usage flag is a
        # false positive (the generic loader resolves the exact base type).
        loaded.append((target, interceptor_class()))  # pyright: ignore[reportAbstractUsage]
    return InterceptorChain(loaded)


def _hook_runner() -> HookRunner:
    """Build the lifecycle hook runner from ``[[hooks]]`` config.

    Each entry's ``spec`` may be a plugin id (resolved through the plugin source, the same
    as a ``[callers]`` reference) or a direct ``"module:Class"`` / ``"/path.py:Class"``
    spec. A configured-but-unloadable hook raises (``PluginError``/``SpecLoadError``, which
    the CLI surfaces) rather than being silently skipped — a config typo should not quietly
    disable a hook the user asked for. The phase is pre-validated by :func:`config.hooks`.

    Returns:
        The configured runner (empty — a no-op — when none are configured).
    """
    plugins = build_plugin_source()
    loaded: list[tuple[HookPhase, str | None, HookPort]] = []
    for phase, spec, client in config.hooks():
        hook_class = load_class(plugins.resolve_hook(spec), HookPort)
        # load_class guarantees a concrete subclass; the abstract-usage flag is a
        # false positive (the generic loader resolves the exact base type).
        loaded.append((HookPhase(phase), client, hook_class()))  # pyright: ignore[reportAbstractUsage]
    return HookRunner(loaded)


def build_start_job() -> StartJob:
    """Build the StartJob use case wired to the filesystem store and default callers.

    Returns:
        A ready-to-run StartJob.
    """
    interceptors = _interceptor_chain()
    return StartJobUseCase(
        store=SqliteSessionStore(_ledger()),
        workflows=_workflow_source(interceptors),
        callers=DefaultCliCallerProvider(
            config.caller_overrides(),
            metering=SqlitePerTurnStore(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
        ),
        uuid_factory=lambda: str(uuid.uuid4()),
        credentials=FilesystemCredentialsStore(paths.CREDENTIALS),
        hooks=_hook_runner(),
        greeting=lambda: build_render_greeting().execute(),
        capability_card=_capability_card,
    )


def _capability_card() -> str | None:
    """The ambient capability card in the active language, or ``None`` when it is off.

    Off by default; enabled via ``[ambient] capability_card``. A static, localised "how do
    I … in gmlw" card the client can answer from mid-session.
    """
    if not config.ambient_capability_card():
        return None
    return active().t("ambient.card")


def build_list_jobs() -> ListJobs:
    """Build the ListJobs use case wired to the filesystem store.

    Returns:
        A ready-to-run ListJobs.
    """
    return ListJobsUseCase(store=SqliteSessionStore(_ledger()))


def build_list_sessions() -> ListSessions:
    """Build the ListSessions use case wired to the filesystem store.

    Returns:
        A ready-to-run ListSessions.
    """
    return ListSessionsUseCase(store=SqliteSessionStore(_ledger()))


def build_list_workflows() -> ListWorkflows:
    """Build the ListWorkflows use case wired to the filesystem workflow source.

    Returns:
        A ready-to-run ListWorkflows.
    """
    return ListWorkflowsUseCase(workflows=_workflow_source(InterceptorChain(())))


def build_workflow_chooser() -> TtyWorkflowChooser:
    """Build the pre-launch workflow chooser for ``gmlw run`` with no workflow.

    Returns:
        A terminal chooser that offers the runnable workflows, or declines off a TTY.
    """
    return TtyWorkflowChooser(build_localizer())


def build_guided_chooser() -> TtyGuidedChooser:
    """Build the guided-vs-quick authoring chooser for ``workflow new`` / ``edit``.

    Returns:
        A terminal chooser that asks whether to author with the guided experience.
    """
    return TtyGuidedChooser(build_localizer())


def build_set_credential() -> SetCredential:
    """Build the SetCredential use case wired to the filesystem credentials store.

    Returns:
        A ready-to-run SetCredential.
    """
    return SetCredentialUseCase(store=FilesystemCredentialsStore(paths.CREDENTIALS))


def build_bootstrap() -> Bootstrap:
    """Build the Bootstrap use case wired to the filesystem layout seeder.

    Returns:
        A ready-to-run Bootstrap.
    """
    return BootstrapUseCase(seeder=FilesystemLayoutSeeder(paths.HOME))


def build_config_commands() -> ConfigCommands:
    """Build the ConfigCommands use case wired to the tomlkit config writer.

    Returns:
        A ready-to-run ConfigCommands, writing to ``~/.gmlw/config.toml``.
    """
    return UpdateConfigUseCase(writer=TomlkitConfigWriter(), config_file=config.config_path)


def build_migrate_layout() -> MigrateLayout:
    """Build the MigrateLayout use case: wrap the old layout into the active environment.

    Reads the persisted ``default_environment`` at call time, so it runs correctly after
    init has written it (and idempotently on every later run).

    Returns:
        A ready-to-run MigrateLayout.
    """
    return MigrateLayoutUseCase(
        FilesystemLayoutMigrator(paths.HOME),
        environment=config.default_environment,
    )


def build_migrate_slugs() -> MigrateSlugs:
    """Build the MigrateSlugs use case: rename legacy raw-named role/environment folders.

    Idempotent — a no-op once every folder is already a clean slug.

    Returns:
        A ready-to-run MigrateSlugs.
    """
    return MigrateSlugsUseCase(FilesystemSlugMigrator(paths.HOME))


def build_init() -> Init:
    """Build the Init use case wired to the ordered-setup ports and step defaults.

    The seed localiser (for the language step and as every chooser's fallback) resolves
    from ``[language] code`` if a prior run set it, else ``$LANG``; the use case rebuilds
    it in the chosen language once step one completes.

    Returns:
        A ready-to-run Init that runs the forced setup and persists it.
    """
    seed_language = resolve_language(config.language() or os.environ.get("LANG"))
    seed_i18n = load_localizer(seed_language)
    return InitUseCase(
        detector=PathClientDetector(),
        seeder=FilesystemLayoutSeeder(paths.HOME),
        language_chooser=TtyLanguageChooser(seed_i18n),
        text_prompt=TtyTextPrompt(seed_i18n),
        axis_chooser=TtyAxisChooser(seed_i18n),
        personas=build_persona_source(),
        persona_chooser=TtyPersonaChooser(seed_i18n),
        client_setup=TtyClientSetup(
            seed_i18n,
            version=HttpClientVersions(),
            runner=SubprocessCommandRunner(),
            clipboard=SystemClipboard(),
        ),
        localizer_factory=load_localizer,
        languages=list(SUPPORTED_LANGUAGES),
        default_language=seed_language,
        default_name=getpass.getuser(),
        version=__version__,
    )


def build_localizer() -> Localizer:
    """Build the localiser for the language the wrapper speaks to the user.

    Prefers the init-chosen ``[language] code``; falls back to ``$LANG`` (English when
    unset or unsupported) until init has run.

    Returns:
        A ready-to-use localiser.
    """
    return load_localizer(resolve_language(config.language() or os.environ.get("LANG")))


def build_check_client_ready() -> CheckClientReady:
    """Build the CheckClientReady use case wired to config overrides and PATH detection.

    Returns:
        A ready-to-run CheckClientReady.
    """
    return CheckClientReadyUseCase(
        overrides=config.caller_overrides(),
        detector=PathClientDetector(),
    )


def build_export_usage() -> ExportUsage:
    """Build the ExportUsage use case wired to the filesystem usage store.

    Returns:
        A ready-to-run ExportUsage.
    """
    return ExportUsageUseCase(
        usage=SqliteUsageStore(_ledger()),
        turns=SqlitePerTurnStore(_ledger()),
    )


def build_render_statusline(client: str | None = None) -> RenderStatusline:
    """Build the RenderStatusline use case, with the client's own status parser.

    The status line renders for the clients that host one (claude, cursor); each
    parses its own payload (both are Claude-Code-compatible for model/context, but
    the allowance block differs -- claude's rate-limit quota vs cursor's plan pools).

    Args:
        client: The client whose payload is being parsed (from ``GMLW_CLIENT``);
            selects the parser. Absent/unknown falls back to the Claude parser.

    Returns:
        A ready-to-run RenderStatusline.
    """
    return RenderStatuslineUseCase(
        parser=_status_parser(client),
        usage=SqliteUsageStore(_ledger()),
        workspace=LocalGitWorkspaceInspector(),
        turns=SqlitePerTurnStore(_ledger()),
    )


def _status_parser(client: str | None) -> ClientStatusParserPort:
    """Select the status-payload parser for a client."""
    if client == "cursor":
        return CursorStatusParser()
    return ClaudeStatusParser()


def build_new_workflow() -> NewWorkflow:
    """Build the NewWorkflow use case wired to its outbound adapters.

    Returns:
        A ready-to-run NewWorkflow.
    """
    interceptors = _interceptor_chain()
    return NewWorkflowUseCase(
        workflows=_workflow_source(interceptors),
        store=SqliteSessionStore(_ledger(), kind="authoring"),
        callers=DefaultCliCallerProvider(
            config.caller_overrides(),
            metering=SqlitePerTurnStore(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
        ),
        uuid_factory=lambda: str(uuid.uuid4()),
        hooks=_hook_runner(),
    )


def build_edit_workflow() -> EditWorkflow:
    """Build the EditWorkflow use case wired to its outbound adapters.

    Returns:
        A ready-to-run EditWorkflow.
    """
    interceptors = _interceptor_chain()
    return EditWorkflowUseCase(
        workflows=_workflow_source(interceptors),
        store=SqliteSessionStore(_ledger(), kind="authoring"),
        callers=DefaultCliCallerProvider(
            config.caller_overrides(),
            metering=SqlitePerTurnStore(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
        ),
        uuid_factory=lambda: str(uuid.uuid4()),
        hooks=_hook_runner(),
    )
