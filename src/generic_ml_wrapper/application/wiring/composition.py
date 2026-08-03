# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The composition root: build the wired inbound use cases."""

from __future__ import annotations

import getpass
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_axis_catalog import (
    FilesystemAxisCatalog,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_migrator import (
    FilesystemLayoutMigrator,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_seeder import (
    FilesystemLayoutSeeder,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_rule_catalog import (
    FilesystemRuleCatalog,
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
from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnostics
from generic_ml_wrapper.adapter.outbound.diagnostics.rolling_file_diagnostics import (
    RollingFileDiagnostics,
)
from generic_ml_wrapper.adapter.outbound.diagnostics.stderr_diagnostics import StderrDiagnostics
from generic_ml_wrapper.adapter.outbound.diagnostics.tee_diagnostics import TeeDiagnostics
from generic_ml_wrapper.adapter.outbound.persona.filesystem_persona_source import (
    FilesystemPersonaSource,
)
from generic_ml_wrapper.adapter.outbound.plugin.filesystem_plugin_source import (
    FilesystemPluginSource,
)
from generic_ml_wrapper.adapter.outbound.status.claude_status_parser import ClaudeStatusParser
from generic_ml_wrapper.adapter.outbound.status.cursor_status_parser import CursorStatusParser
from generic_ml_wrapper.adapter.outbound.store.filesystem_artifact_purge import (
    FilesystemArtifactPurge,
)
from generic_ml_wrapper.adapter.outbound.store.filesystem_report_exporter import (
    FilesystemReportExporter,
)
from generic_ml_wrapper.adapter.outbound.store.filesystem_transcript_store import (
    FilesystemTranscriptStore,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_ledger_purge import SqliteLedgerPurge
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStore
from generic_ml_wrapper.adapter.outbound.update.pypi_version_checker import PypiVersionChecker
from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_source import (
    FilesystemWorkflowSource,
)
from generic_ml_wrapper.adapter.outbound.workflow.zip_workflow_archive import ZipWorkflowArchive
from generic_ml_wrapper.adapter.outbound.workspace.local_workspace_inspector import (
    LocalGitWorkspaceInspector,
)
from generic_ml_wrapper.application.domain.service.hook import HookPhase
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.port.inbound.bootstrap import Bootstrap
from generic_ml_wrapper.application.port.inbound.check_client_ready import CheckClientReady
from generic_ml_wrapper.application.port.inbound.check_for_update import CheckForUpdate
from generic_ml_wrapper.application.port.inbound.config_commands import ConfigCommands
from generic_ml_wrapper.application.port.inbound.create_axis import CreateAxis
from generic_ml_wrapper.application.port.inbound.delete_jobs import DeleteJobs
from generic_ml_wrapper.application.port.inbound.delete_sessions import DeleteSessions
from generic_ml_wrapper.application.port.inbound.edit_workflow import EditWorkflow
from generic_ml_wrapper.application.port.inbound.export_usage import ExportUsage
from generic_ml_wrapper.application.port.inbound.export_workflow import ExportWorkflow
from generic_ml_wrapper.application.port.inbound.import_workflow import ImportWorkflow
from generic_ml_wrapper.application.port.inbound.init import Init
from generic_ml_wrapper.application.port.inbound.list_clients import ListClients
from generic_ml_wrapper.application.port.inbound.list_drafts import ListDrafts
from generic_ml_wrapper.application.port.inbound.list_jobs import ListJobs
from generic_ml_wrapper.application.port.inbound.list_launch_clients import ListLaunchClients
from generic_ml_wrapper.application.port.inbound.list_personas import ListPersonas
from generic_ml_wrapper.application.port.inbound.list_plugins import ListPlugins
from generic_ml_wrapper.application.port.inbound.list_rules import ListRules
from generic_ml_wrapper.application.port.inbound.list_sessions import ListSessions
from generic_ml_wrapper.application.port.inbound.list_workflow_catalog import ListWorkflowCatalog
from generic_ml_wrapper.application.port.inbound.list_workflows import ListWorkflows
from generic_ml_wrapper.application.port.inbound.migrate_layout import MigrateLayout
from generic_ml_wrapper.application.port.inbound.migrate_slugs import MigrateSlugs
from generic_ml_wrapper.application.port.inbound.new_workflow import NewWorkflow
from generic_ml_wrapper.application.port.inbound.render_greeting import RenderGreeting
from generic_ml_wrapper.application.port.inbound.render_statusline import RenderStatusline
from generic_ml_wrapper.application.port.inbound.save_usage_report import SaveUsageReport
from generic_ml_wrapper.application.port.inbound.set_credential import SetCredential
from generic_ml_wrapper.application.port.inbound.start_job import StartJob
from generic_ml_wrapper.application.port.outbound.artifact_purge import ArtifactPurgePort
from generic_ml_wrapper.application.port.outbound.axis_catalog import AxisCatalogPort
from generic_ml_wrapper.application.port.outbound.client_status import ClientStatusParserPort
from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort
from generic_ml_wrapper.application.port.outbound.hook import HookPort
from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort
from generic_ml_wrapper.application.usecase.bootstrap import BootstrapUseCase
from generic_ml_wrapper.application.usecase.check_client_ready import CheckClientReadyUseCase
from generic_ml_wrapper.application.usecase.check_for_update import CheckForUpdateUseCase
from generic_ml_wrapper.application.usecase.create_axis import CreateAxisUseCase
from generic_ml_wrapper.application.usecase.delete_jobs import DeleteJobsUseCase
from generic_ml_wrapper.application.usecase.delete_sessions import DeleteSessionsUseCase
from generic_ml_wrapper.application.usecase.edit_workflow import EditWorkflowUseCase
from generic_ml_wrapper.application.usecase.export_usage import ExportUsageUseCase
from generic_ml_wrapper.application.usecase.export_workflow import ExportWorkflowUseCase
from generic_ml_wrapper.application.usecase.import_workflow import ImportWorkflowUseCase
from generic_ml_wrapper.application.usecase.init import InitUseCase
from generic_ml_wrapper.application.usecase.list_clients import ListClientsUseCase
from generic_ml_wrapper.application.usecase.list_drafts import ListDraftsUseCase
from generic_ml_wrapper.application.usecase.list_jobs import ListJobsUseCase
from generic_ml_wrapper.application.usecase.list_launch_clients import ListLaunchClientsUseCase
from generic_ml_wrapper.application.usecase.list_personas import ListPersonasUseCase
from generic_ml_wrapper.application.usecase.list_plugins import ListPluginsUseCase
from generic_ml_wrapper.application.usecase.list_rules import ListRulesUseCase
from generic_ml_wrapper.application.usecase.list_sessions import ListSessionsUseCase
from generic_ml_wrapper.application.usecase.list_workflow_catalog import (
    ListWorkflowCatalogUseCase,
)
from generic_ml_wrapper.application.usecase.list_workflows import ListWorkflowsUseCase
from generic_ml_wrapper.application.usecase.migrate_layout import MigrateLayoutUseCase
from generic_ml_wrapper.application.usecase.migrate_slugs import MigrateSlugsUseCase
from generic_ml_wrapper.application.usecase.new_workflow import NewWorkflowUseCase
from generic_ml_wrapper.application.usecase.render_greeting import RenderGreetingUseCase
from generic_ml_wrapper.application.usecase.render_statusline import RenderStatuslineUseCase
from generic_ml_wrapper.application.usecase.save_usage_report import SaveUsageReportUseCase
from generic_ml_wrapper.application.usecase.set_credential import SetCredentialUseCase
from generic_ml_wrapper.application.usecase.start_job import StartJobUseCase
from generic_ml_wrapper.application.usecase.update_config import UpdateConfigUseCase
from generic_ml_wrapper.application.wiring.paths import paths
from generic_ml_wrapper.application.wiring.spec_loader import SpecLoader
from generic_ml_wrapper.common import config
from generic_ml_wrapper.common.i18n import (
    SUPPORTED_LANGUAGES,
    Localizer,
    active,
    load_localizer,
    resolve_language,
)


def _ledger() -> Ledger:
    """The shared SQLite ledger backing the session/turn/usage stores."""
    return Ledger(paths.ledger)


def _transcript_root() -> Path:
    """Where transcripts are written: the configured root, else the default.

    Shared by the writer and the purge. Resolving it in one place is what keeps a delete
    honest for a user who moved their transcripts: sweeping the default root while they
    record into their own would leave behind precisely the files they asked to be rid of.
    """
    settings = config.transcript()
    return Path(settings.root) if settings.root else paths.transcripts


def _transcript() -> TranscriptPort | None:
    """The transcript store when ``[transcript]`` is enabled, else ``None`` (off)."""
    if not config.transcript().enabled:
        return None
    return FilesystemTranscriptStore(_transcript_root())


def _artifact_purge() -> ArtifactPurgePort:
    """The purge for the two artifact roots: compiled contexts and transcripts.

    Built from the transcript root regardless of whether transcripts are *currently*
    enabled -- they may have been on when the sessions being deleted ran, and their files
    outlive the setting.
    """
    return FilesystemArtifactPurge(paths.contexts, _transcript_root())


def _workflow_source(interceptors: InterceptorChain) -> FilesystemWorkflowSource:
    """Build the filesystem workflow source with the standard ``~/.gmlw`` roots.

    Args:
        interceptors: The interceptor chain applied to context sections at compile.

    Returns:
        A workflow source that compiles context from workflows, profile, and rules.
    """
    return FilesystemWorkflowSource(
        paths.workflows,
        paths.profile,
        paths.templates,
        interceptors,
        personas=build_persona_source(),
        compressor=CacheBackedContextCompressor(),
        startup=config.startup,
        companion=lambda: config.companion().persona,
        environments_root=paths.environments,
        default_environment=config.default_environment,
        default_role=config.default_role,
        user_name=lambda: config.companion().name,
        language=config.language,
    )


def build_persona_source() -> FilesystemPersonaSource:
    """Build the filesystem persona source rooted at ``~/.gmlw/personas``.

    Returns:
        A persona source that seeds and reads the packaged personas.
    """
    return FilesystemPersonaSource(paths.personas)


def build_list_personas() -> ListPersonas:
    """Build the ListPersonas use case wired to the persona source.

    Returns:
        A ready-to-run ListPersonas.
    """
    return ListPersonasUseCase(build_persona_source())


def build_list_clients() -> ListClients:
    """Build the ListClients use case: PATH detection + version reads + the default setting.

    Returns:
        A ready-to-run ListClients.
    """
    return ListClientsUseCase(
        detector=PathClientDetector(),
        version=HttpClientVersions(),
        default_client=config.default_client,
    )


def build_list_launch_clients() -> ListLaunchClients:
    """Build the ListLaunchClients use case: PATH, ``[callers]``, and the default.

    No version reads, unlike :func:`build_list_clients` — this one sits between a user
    saying "launch" and the launch happening.

    Returns:
        A ready-to-run ListLaunchClients.
    """
    return ListLaunchClientsUseCase(
        detector=PathClientDetector(),
        default_client=config.default_client,
        caller_overrides=config.caller_overrides,
    )


def build_plugin_source() -> FilesystemPluginSource:
    """Build the filesystem plugin source rooted at ``~/.gmlw/plugins``.

    Returns:
        A plugin source that lists plugins and resolves id references.
    """
    return FilesystemPluginSource(paths.plugins)


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


def build_check_for_update() -> CheckForUpdate:
    """Build the CheckForUpdate use case wired to PyPI and its local cache file.

    Returns:
        A ready-to-run CheckForUpdate (free, cached, at most one network call a day).
    """
    return CheckForUpdateUseCase(
        checker=PypiVersionChecker(),
        current_version=__version__,
        package="generic-ml-wrapper",
        enabled=config.update_check,
        clock=lambda: datetime.now(UTC),
        cache_path=paths.state / "update-check.json",
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
        interceptor_class = SpecLoader().load_class(spec, InterceptorPort)
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
        hook_class = SpecLoader().load_class(plugins.resolve_hook(spec), HookPort)
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
    sessions = SqliteSessionStore(_ledger())
    return StartJobUseCase(
        store=sessions,
        workflows=_workflow_source(interceptors),
        callers=DefaultCliCallerProvider(
            config.caller_overrides(),
            metering=SqlitePerTurnStore(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
            sessions=sessions,
        ),
        uuid_factory=lambda: str(uuid.uuid4()),
        cwd_factory=os.getcwd,
        credentials=FilesystemCredentialsStore(paths.credentials),
        hooks=_hook_runner(),
        greeting=lambda: build_render_greeting().execute(),
        capability_card=_capability_card,
        client_args=config.client_args_for,
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
    """Build the ListSessions use case wired to the session and usage stores.

    Returns:
        A ready-to-run ListSessions.
    """
    return ListSessionsUseCase(
        store=SqliteSessionStore(_ledger()),
        turns=SqlitePerTurnStore(_ledger()),
        usage=SqliteUsageStore(_ledger()),
    )


def build_delete_sessions() -> DeleteSessions:
    """Build the DeleteSessions use case wired to the stores and both purges.

    Returns:
        A ready-to-run DeleteSessions.
    """
    return DeleteSessionsUseCase(
        store=SqliteSessionStore(_ledger()),
        turns=SqlitePerTurnStore(_ledger()),
        usage=SqliteUsageStore(_ledger()),
        ledger=SqliteLedgerPurge(_ledger()),
        artifacts=_artifact_purge(),
    )


def build_delete_jobs() -> DeleteJobs:
    """Build the DeleteJobs use case wired to the stores and both purges.

    The session store is the default ``work``-scoped one, so ``authoring`` jobs are
    unreachable here exactly as they are unreachable from ``gmlw jobs``.

    Returns:
        A ready-to-run DeleteJobs.
    """
    return DeleteJobsUseCase(
        store=SqliteSessionStore(_ledger()),
        turns=SqlitePerTurnStore(_ledger()),
        usage=SqliteUsageStore(_ledger()),
        ledger=SqliteLedgerPurge(_ledger()),
        artifacts=_artifact_purge(),
    )


def build_export_workflow() -> ExportWorkflow:
    """Build the ExportWorkflow use case wired to the zip archive under ~/.gmlw/exports.

    Returns:
        A ready-to-run ExportWorkflow.
    """
    return ExportWorkflowUseCase(
        workflows=_workflow_source(InterceptorChain(())),
        archive=ZipWorkflowArchive(paths.exports, lambda: datetime.now(UTC)),
    )


def build_import_workflow() -> ImportWorkflow:
    """Build the ImportWorkflow use case wired to the zip archive and the backup root.

    Returns:
        A ready-to-run ImportWorkflow.
    """
    return ImportWorkflowUseCase(
        workflows=_workflow_source(InterceptorChain(())),
        archive=ZipWorkflowArchive(paths.exports, lambda: datetime.now(UTC)),
        backups_root=paths.workflow_backups,
        clock=lambda: datetime.now(UTC),
    )


def build_list_workflow_catalog() -> ListWorkflowCatalog:
    """Build the ListWorkflowCatalog use case wired to the filesystem workflow source.

    Returns:
        A ready-to-run ListWorkflowCatalog.
    """
    return ListWorkflowCatalogUseCase(workflows=_workflow_source(InterceptorChain(())))


def build_list_drafts() -> ListDrafts:
    """Build the ListDrafts use case wired to the filesystem workflow source.

    Returns:
        A ready-to-run ListDrafts.
    """
    return ListDraftsUseCase(workflows=_workflow_source(InterceptorChain(())))


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
    return SetCredentialUseCase(store=FilesystemCredentialsStore(paths.credentials))


def build_bootstrap() -> Bootstrap:
    """Build the Bootstrap use case wired to the filesystem layout seeder.

    Returns:
        A ready-to-run Bootstrap.
    """
    return BootstrapUseCase(seeder=FilesystemLayoutSeeder(paths.home))


def build_config_commands() -> ConfigCommands:
    """Build the ConfigCommands use case wired to the tomlkit config writer.

    Returns:
        A ready-to-run ConfigCommands, writing to ``~/.gmlw/config.toml``.
    """
    return UpdateConfigUseCase(writer=TomlkitConfigWriter(), config_file=config.config_path)


def build_create_axis() -> CreateAxis:
    """Build the CreateAxis use case wired to the filesystem catalog and config writer.

    Returns:
        A ready-to-run CreateAxis, creating folders under ``~/.gmlw`` and, when asked,
        pointing ``profile.default_<kind>`` at the new slug in ``config.toml``.
    """
    return CreateAxisUseCase(
        catalog=FilesystemAxisCatalog(paths.home),
        writer=TomlkitConfigWriter(),
        config_file=config.config_path,
        clock=lambda: datetime.now(UTC).astimezone(),
    )


def build_axis_catalog() -> AxisCatalogPort:
    """Build the role/environment catalog reader over ``~/.gmlw``.

    Returns:
        A ready-to-use :class:`AxisCatalogPort` for listing the axis slug-folders.
    """
    return FilesystemAxisCatalog(paths.home)


def build_list_rules() -> ListRules:
    """Build the ListRules use case for the TUI's Rules browser.

    Returns:
        A ready-to-run ListRules over the environment and role rule folders.
    """
    return ListRulesUseCase(
        catalog=FilesystemRuleCatalog(paths.home, FilesystemAxisCatalog(paths.home))
    )


def build_migrate_layout() -> MigrateLayout:
    """Build the MigrateLayout use case: wrap the old layout into the active environment.

    Reads the persisted ``default_environment`` at call time, so it runs correctly after
    init has written it (and idempotently on every later run).

    Returns:
        A ready-to-run MigrateLayout.
    """
    return MigrateLayoutUseCase(
        FilesystemLayoutMigrator(paths.home),
        environment=config.default_environment,
    )


def build_migrate_slugs() -> MigrateSlugs:
    """Build the MigrateSlugs use case: rename legacy raw-named role/environment folders.

    Idempotent — a no-op once every folder is already a clean slug.

    Returns:
        A ready-to-run MigrateSlugs.
    """
    return MigrateSlugsUseCase(FilesystemSlugMigrator(paths.home))


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
        seeder=FilesystemLayoutSeeder(paths.home),
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


def build_save_usage_report() -> SaveUsageReport:
    """Build the SaveUsageReport use case: the report source plus the filesystem JSON writer.

    Returns:
        A ready-to-run SaveUsageReport writing to ``~/.gmlw/exports``.
    """
    return SaveUsageReportUseCase(
        export=build_export_usage(),
        exporter=FilesystemReportExporter(
            paths.exports, clock=lambda: datetime.now(UTC).astimezone()
        ),
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
    sessions = SqliteSessionStore(_ledger(), kind="authoring")
    return NewWorkflowUseCase(
        workflows=_workflow_source(interceptors),
        store=sessions,
        callers=DefaultCliCallerProvider(
            config.caller_overrides(),
            metering=SqlitePerTurnStore(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
            sessions=sessions,
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
    sessions = SqliteSessionStore(_ledger(), kind="authoring")
    return EditWorkflowUseCase(
        workflows=_workflow_source(interceptors),
        store=sessions,
        callers=DefaultCliCallerProvider(
            config.caller_overrides(),
            metering=SqlitePerTurnStore(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
            sessions=sessions,
        ),
        uuid_factory=lambda: str(uuid.uuid4()),
        hooks=_hook_runner(),
    )


def build_diagnostics(
    *,
    quiet: bool = False,
    to_stderr: bool = True,
    path: Path | None = None,
) -> DiagnosticsPort:
    """Build the diagnostics sink from the resolved logging policy.

    Level comes from ``GMLW_LOG_LEVEL`` or ``[logging] level``; the file destination and
    its rotation from ``[logging] to_file / max_bytes / backup_count``. Nothing below the
    threshold is written, and every sink honours the never-raises contract, so a broken
    logging setup degrades to silence rather than to a failed run.

    Args:
        quiet: Discard everything. For the statusline: it renders into another program's
            prompt many times a session, from a short-lived subprocess, so it must neither
            write a byte to the shared stream nor race the others for the rolling file.
        to_stderr: Also write to stderr. True for a utility command a person is watching;
            **false for any command that hands the terminal to a client** — there stderr
            is the client's own screen, and a line written to it corrupts the client's
            display and is lost on the next redraw (issue #59).
        path: An explicit config file (for tests); defaults to ``~/.gmlw/config.toml``.

    Returns:
        The sink to install with ``log.set_active``.
    """
    if quiet:
        return NullDiagnostics()
    level = os.environ.get("GMLW_LOG_LEVEL") or config.log_level(path)
    sinks: list[DiagnosticsPort] = []
    if config.log_to_file(path):
        sinks.append(
            RollingFileDiagnostics(
                paths.log_file,
                level=level,
                max_bytes=config.log_max_bytes(path),
                backup_count=config.log_backup_count(path),
            )
        )
    if to_stderr:
        sinks.append(StderrDiagnostics(level=level))
    if not sinks:
        return NullDiagnostics()
    return sinks[0] if len(sinks) == 1 else TeeDiagnostics(*sinks)
