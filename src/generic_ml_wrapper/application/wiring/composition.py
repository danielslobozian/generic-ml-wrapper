# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The composition root: build the wired inbound use cases."""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_guided_chooser import TtyGuidedChooser
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_workflow_chooser import TtyWorkflowChooser
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_axis_catalog import (
    FilesystemAxisCatalogAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_migrator import (
    FilesystemLayoutMigratorAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_seeder import (
    FilesystemLayoutSeederAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_rule_catalog import (
    FilesystemRuleCatalogAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_slug_migrator import (
    FilesystemSlugMigratorAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_working_folder import (
    FilesystemWorkingFolderAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.http_client_versions import (
    HttpClientVersionsAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.module_build_info import ModuleBuildInfoAdapter
from generic_ml_wrapper.adapter.outbound.bootstrap.os_system_info import OsSystemInfoAdapter
from generic_ml_wrapper.adapter.outbound.bootstrap.path_client_detector import (
    PathClientDetectorAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.toml_client_catalog import (
    TomlClientCatalogAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_secret_prompt import TtySecretPromptAdapter
from generic_ml_wrapper.adapter.outbound.caller.default_provider import (
    DefaultCliCallerProviderAdapter,
)
from generic_ml_wrapper.adapter.outbound.caller.environment_run_handoff import (
    EnvironmentRunHandoffAdapter,
)
from generic_ml_wrapper.adapter.outbound.caller.signal_interrupt_scope import (
    SignalInterruptScopeAdapter,
)
from generic_ml_wrapper.adapter.outbound.compress.cache_backed_compressor import (
    CacheBackedContextCompressorAdapter,
)
from generic_ml_wrapper.adapter.outbound.config import toml_config_reader as config
from generic_ml_wrapper.adapter.outbound.config.toml_runtime_config import TomlRuntimeConfigAdapter
from generic_ml_wrapper.adapter.outbound.config.toml_settings_catalog import (
    TomlSettingsCatalogAdapter,
)
from generic_ml_wrapper.adapter.outbound.config.tomlkit_config_writer import (
    TomlkitConfigWriterAdapter,
)
from generic_ml_wrapper.adapter.outbound.credentials.filesystem_credentials_store import (
    FilesystemCredentialsStoreAdapter,
)
from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnosticsAdapter
from generic_ml_wrapper.adapter.outbound.diagnostics.rolling_file_diagnostics import (
    RollingFileDiagnosticsAdapter,
)
from generic_ml_wrapper.adapter.outbound.diagnostics.stderr_diagnostics import (
    StderrDiagnosticsAdapter,
)
from generic_ml_wrapper.adapter.outbound.diagnostics.tee_diagnostics import TeeDiagnosticsAdapter
from generic_ml_wrapper.adapter.outbound.i18n.json_catalog_localizer import (
    JsonCatalogLanguageCatalogAdapter,
)
from generic_ml_wrapper.adapter.outbound.persona.filesystem_persona_source import (
    FilesystemPersonaSourceAdapter,
)
from generic_ml_wrapper.adapter.outbound.plugin.filesystem_plugin_source import (
    FilesystemPluginSourceAdapter,
)
from generic_ml_wrapper.adapter.outbound.status.catalogued_status_parsers import (
    CataloguedStatusParsersAdapter,
)
from generic_ml_wrapper.adapter.outbound.store.filesystem_artifact_purge import (
    FilesystemArtifactPurgeAdapter,
)
from generic_ml_wrapper.adapter.outbound.store.filesystem_report_exporter import (
    FilesystemReportExporterAdapter,
)
from generic_ml_wrapper.adapter.outbound.store.filesystem_session_lock import (
    FilesystemSessionLockAdapter,
)
from generic_ml_wrapper.adapter.outbound.store.filesystem_transcript_store import (
    FilesystemTranscriptStoreAdapter,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_ledger_purge import SqliteLedgerPurgeAdapter
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import (
    SqlitePerTurnStoreAdapter,
)
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStoreAdapter
from generic_ml_wrapper.adapter.outbound.store.sqlite_store_migration import (
    SqliteStoreMigrationAdapter,
)
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStoreAdapter
from generic_ml_wrapper.adapter.outbound.update.filesystem_update_cache import (
    FilesystemUpdateCacheAdapter,
)
from generic_ml_wrapper.adapter.outbound.update.pypi_version_checker import (
    PypiVersionCheckerAdapter,
)
from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_backup import (
    FilesystemWorkflowBackupAdapter,
)
from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_source import (
    FilesystemWorkflowSourceAdapter,
)
from generic_ml_wrapper.adapter.outbound.workflow.zip_workflow_archive import (
    ZipWorkflowArchiveAdapter,
)
from generic_ml_wrapper.adapter.outbound.workspace.local_workspace_inspector import (
    LocalGitWorkspaceInspectorAdapter,
)
from generic_ml_wrapper.application.domain.model.hook_phase import HookPhase
from generic_ml_wrapper.application.port.inbound.application_settings import (
    ApplicationSettingsUseCase,
)
from generic_ml_wrapper.application.port.inbound.bootstrap import BootstrapUseCase
from generic_ml_wrapper.application.port.inbound.check_client_ready import CheckClientReadyUseCase
from generic_ml_wrapper.application.port.inbound.check_for_update import CheckForUpdateUseCase
from generic_ml_wrapper.application.port.inbound.check_launch_location import (
    CheckLaunchLocationUseCase,
)
from generic_ml_wrapper.application.port.inbound.check_store_contract import (
    CheckStoreContractUseCase,
)
from generic_ml_wrapper.application.port.inbound.compose_statusline import ComposeStatuslineUseCase
from generic_ml_wrapper.application.port.inbound.config_commands import ConfigCommandsUseCase
from generic_ml_wrapper.application.port.inbound.create_axis import CreateAxisUseCase
from generic_ml_wrapper.application.port.inbound.delete_jobs import DeleteJobsUseCase
from generic_ml_wrapper.application.port.inbound.delete_sessions import DeleteSessionsUseCase
from generic_ml_wrapper.application.port.inbound.describe_build import DescribeBuildUseCase
from generic_ml_wrapper.application.port.inbound.edit_workflow import EditWorkflowUseCase
from generic_ml_wrapper.application.port.inbound.export_usage import ExportUsageUseCase
from generic_ml_wrapper.application.port.inbound.export_workflow import ExportWorkflowUseCase
from generic_ml_wrapper.application.port.inbound.import_workflow import ImportWorkflowUseCase
from generic_ml_wrapper.application.port.inbound.list_authoring_modes import (
    ListAuthoringModesUseCase,
)
from generic_ml_wrapper.application.port.inbound.list_available_languages import (
    ListAvailableLanguagesUseCase,
)
from generic_ml_wrapper.application.port.inbound.list_axis_examples import ListAxisExamplesUseCase
from generic_ml_wrapper.application.port.inbound.list_clients import ListClientsUseCase
from generic_ml_wrapper.application.port.inbound.list_drafts import ListDraftsUseCase
from generic_ml_wrapper.application.port.inbound.list_jobs import ListJobsUseCase
from generic_ml_wrapper.application.port.inbound.list_launch_clients import ListLaunchClientsUseCase
from generic_ml_wrapper.application.port.inbound.list_personas import ListPersonasUseCase
from generic_ml_wrapper.application.port.inbound.list_plugins import ListPluginsUseCase
from generic_ml_wrapper.application.port.inbound.list_rules import ListRulesUseCase
from generic_ml_wrapper.application.port.inbound.list_sessions import ListSessionsUseCase
from generic_ml_wrapper.application.port.inbound.list_supported_clients import (
    ListSupportedClientsUseCase,
)
from generic_ml_wrapper.application.port.inbound.list_workflow_catalog import (
    ListWorkflowCatalogUseCase,
)
from generic_ml_wrapper.application.port.inbound.list_workflows import ListWorkflowsUseCase
from generic_ml_wrapper.application.port.inbound.migrate_layout import MigrateLayoutUseCase
from generic_ml_wrapper.application.port.inbound.migrate_slugs import MigrateSlugsUseCase
from generic_ml_wrapper.application.port.inbound.new_workflow import NewWorkflowUseCase
from generic_ml_wrapper.application.port.inbound.save_init_answers import (
    SaveInitAnswersUseCase,
)
from generic_ml_wrapper.application.port.inbound.save_usage_report import SaveUsageReportUseCase
from generic_ml_wrapper.application.port.inbound.set_credential import SetCredentialUseCase
from generic_ml_wrapper.application.port.inbound.start_job import StartJobUseCase
from generic_ml_wrapper.application.port.outbound.artifact_purge import ArtifactPurgePort
from generic_ml_wrapper.application.port.outbound.axis_catalog import AxisCatalogPort
from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort
from generic_ml_wrapper.application.port.outbound.hook import HookPort
from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.application.port.outbound.session_lock import SessionLockPort
from generic_ml_wrapper.application.port.outbound.store_migration import (
    StoreMigrationPort,
)
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort
from generic_ml_wrapper.application.usecase.bootstrap import BootstrapService
from generic_ml_wrapper.application.usecase.check_client_ready import CheckClientReadyService
from generic_ml_wrapper.application.usecase.check_for_update import CheckForUpdateService
from generic_ml_wrapper.application.usecase.check_launch_location import (
    CheckLaunchLocationService,
)
from generic_ml_wrapper.application.usecase.check_store_contract import (
    CheckStoreContractService,
)
from generic_ml_wrapper.application.usecase.compose_statusline import ComposeStatuslineService
from generic_ml_wrapper.application.usecase.create_axis import CreateAxisService
from generic_ml_wrapper.application.usecase.delete_jobs import DeleteJobsService
from generic_ml_wrapper.application.usecase.delete_sessions import DeleteSessionsService
from generic_ml_wrapper.application.usecase.describe_build import DescribeBuildService
from generic_ml_wrapper.application.usecase.edit_workflow import EditWorkflowService
from generic_ml_wrapper.application.usecase.export_usage import ExportUsageService
from generic_ml_wrapper.application.usecase.export_workflow import ExportWorkflowService
from generic_ml_wrapper.application.usecase.hook_runner import HookRunner
from generic_ml_wrapper.application.usecase.import_workflow import ImportWorkflowService
from generic_ml_wrapper.application.usecase.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.usecase.launch import LaunchSequence
from generic_ml_wrapper.application.usecase.list_authoring_modes import ListAuthoringModesService
from generic_ml_wrapper.application.usecase.list_available_languages import (
    ListAvailableLanguagesService,
)
from generic_ml_wrapper.application.usecase.list_axis_examples import ListAxisExamplesService
from generic_ml_wrapper.application.usecase.list_clients import ListClientsService
from generic_ml_wrapper.application.usecase.list_drafts import ListDraftsService
from generic_ml_wrapper.application.usecase.list_jobs import ListJobsService
from generic_ml_wrapper.application.usecase.list_launch_clients import ListLaunchClientsService
from generic_ml_wrapper.application.usecase.list_personas import ListPersonasService
from generic_ml_wrapper.application.usecase.list_plugins import ListPluginsService
from generic_ml_wrapper.application.usecase.list_rules import ListRulesService
from generic_ml_wrapper.application.usecase.list_sessions import ListSessionsService
from generic_ml_wrapper.application.usecase.list_supported_clients import (
    ListSupportedClientsService,
)
from generic_ml_wrapper.application.usecase.list_workflow_catalog import (
    ListWorkflowCatalogService,
)
from generic_ml_wrapper.application.usecase.list_workflows import ListWorkflowsService
from generic_ml_wrapper.application.usecase.migrate_layout import MigrateLayoutService
from generic_ml_wrapper.application.usecase.migrate_slugs import MigrateSlugsService
from generic_ml_wrapper.application.usecase.new_workflow import NewWorkflowService
from generic_ml_wrapper.application.usecase.read_application_settings import (
    ReadApplicationSettingsService,
)
from generic_ml_wrapper.application.usecase.save_init_answers import SaveInitAnswersService
from generic_ml_wrapper.application.usecase.save_usage_report import SaveUsageReportService
from generic_ml_wrapper.application.usecase.set_credential import SetCredentialService
from generic_ml_wrapper.application.usecase.start_job import StartJobService
from generic_ml_wrapper.application.usecase.update_config import UpdateConfigService
from generic_ml_wrapper.application.wiring import diagnostics_log as log
from generic_ml_wrapper.application.wiring.localization import (
    MessageSource,
    active,
    load_localizer,
    resolve_language,
)
from generic_ml_wrapper.application.wiring.paths import paths
from generic_ml_wrapper.application.wiring.spec_loader import SpecLoader


def _ledger() -> Ledger:
    """The shared SQLite ledger backing the session/turn/usage stores."""
    return Ledger(paths.ledger)


def _session_locks() -> SessionLockPort:
    """The locks that mark a session as running and refuse to delete one that is."""
    return FilesystemSessionLockAdapter(paths.home)


def build_store_migration() -> StoreMigrationPort:
    """Build the store migration, wired to the ledger's database file.

    Returns:
        A ready-to-run StoreMigrationPort.
    """
    return SqliteStoreMigrationAdapter(
        lambda: sqlite3.connect(paths.ledger, timeout=5.0),
        paths.ledger.parent,
    )


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
    return FilesystemTranscriptStoreAdapter(_transcript_root())


def _artifact_purge() -> ArtifactPurgePort:
    """The purge for the two artifact roots: compiled contexts and transcripts.

    Built from the transcript root regardless of whether transcripts are *currently*
    enabled -- they may have been on when the sessions being deleted ran, and their files
    outlive the setting.
    """
    return FilesystemArtifactPurgeAdapter(paths.contexts, _transcript_root())


def _workflow_source(interceptors: InterceptorChain) -> FilesystemWorkflowSourceAdapter:
    """Build the filesystem workflow source with the standard ``~/.gmlw`` roots.

    Args:
        interceptors: The interceptor chain applied to context sections at compile.

    Returns:
        A workflow source that compiles context from workflows, profile, and rules.
    """
    return FilesystemWorkflowSourceAdapter(
        paths.workflows,
        paths.profile,
        paths.templates,
        interceptors,
        personas=build_persona_source(),
        compressor=CacheBackedContextCompressorAdapter(),
        startup=config.startup,
        companion=lambda: config.companion().persona,
        environments_root=paths.environments,
        default_environment=config.default_environment,
        default_role=config.default_role,
        user_name=lambda: config.companion().name,
        language=config.language,
    )


def build_persona_source() -> FilesystemPersonaSourceAdapter:
    """Build the filesystem persona source rooted at ``~/.gmlw/personas``.

    Returns:
        A persona source that seeds and reads the packaged personas.
    """
    return FilesystemPersonaSourceAdapter(paths.personas)


def build_list_personas() -> ListPersonasUseCase:
    """Build the ListPersonasUseCase use case wired to the persona source.

    Returns:
        A ready-to-run ListPersonasUseCase.
    """
    return ListPersonasService(build_persona_source())


def build_list_clients() -> ListClientsUseCase:
    """Build the ListClientsUseCase use case: PATH detection + version reads + the default setting.

    Returns:
        A ready-to-run ListClientsUseCase.
    """
    return ListClientsService(
        detector=PathClientDetectorAdapter(),
        version=HttpClientVersionsAdapter(),
        default_client=config.default_client,
        catalog=TomlClientCatalogAdapter(),
    )


def build_list_launch_clients() -> ListLaunchClientsUseCase:
    """Build the ListLaunchClientsUseCase use case: PATH, ``[callers]``, and the default.

    No version reads, unlike :func:`build_list_clients` — this one sits between a user
    saying "launch" and the launch happening.

    Returns:
        A ready-to-run ListLaunchClientsUseCase.
    """
    return ListLaunchClientsService(
        detector=PathClientDetectorAdapter(),
        default_client=config.default_client,
        caller_overrides=config.caller_overrides,
        catalog=TomlClientCatalogAdapter(),
    )


def build_plugin_source() -> FilesystemPluginSourceAdapter:
    """Build the filesystem plugin source rooted at ``~/.gmlw/plugins``.

    Returns:
        A plugin source that lists plugins and resolves id references.
    """
    return FilesystemPluginSourceAdapter(paths.plugins)


def build_list_plugins() -> ListPluginsUseCase:
    """Build the ListPluginsUseCase use case wired to the plugin source.

    Returns:
        A ready-to-run ListPluginsUseCase.
    """
    return ListPluginsService(build_plugin_source())


def _persona_greeting() -> str | None:
    """The selected persona's greeting instruction, or ``None`` when there is none.

    The line is the persona's own text, handed to the client unchanged. gmlw composes
    nothing: it does not know the hour in the user's words, and it has no business
    writing prose in a language it picked.
    """
    settings = config.companion()
    if settings.persona is None:
        return None
    persona = build_persona_source().get(settings.persona)
    if persona is None or not persona.greeting.strip():
        return None
    return persona.greeting


def build_check_for_update() -> CheckForUpdateUseCase:
    """Build the CheckForUpdateUseCase use case wired to PyPI and its local cache file.

    Returns:
        A ready-to-run CheckForUpdateUseCase (free, cached, at most one network call a day).
    """
    return CheckForUpdateService(
        checker=PypiVersionCheckerAdapter(),
        current_version=__version__,
        package="generic-ml-wrapper",
        enabled=config.update_check,
        clock=lambda: datetime.now(UTC),
        cache=FilesystemUpdateCacheAdapter(paths.state / "update-check.json", log.active()),
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
    return HookRunner(loaded, log.active())


def _launch_sequence() -> LaunchSequence:
    """Build the bracketed launch sequence shared by every use case that runs a client.

    Returns:
        The sequence, carrying the configured hooks and where a bad teardown is reported.
    """
    return LaunchSequence(
        _hook_runner(),
        log.active(),
        _session_locks(),
        SignalInterruptScopeAdapter(),
    )


def build_start_job() -> StartJobUseCase:
    """Build the StartJobUseCase use case wired to the filesystem store and default callers.

    Returns:
        A ready-to-run StartJobUseCase.
    """
    interceptors = _interceptor_chain()
    sessions = SqliteSessionStoreAdapter(_ledger())
    return StartJobService(
        store=sessions,
        workflows=_workflow_source(interceptors),
        callers=DefaultCliCallerProviderAdapter(
            config.caller_overrides(),
            metering=SqlitePerTurnStoreAdapter(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
            sessions=sessions,
        ),
        uuid_factory=lambda: str(uuid.uuid4()),
        cwd_factory=os.getcwd,
        credentials=FilesystemCredentialsStoreAdapter(paths.credentials),
        launch=_launch_sequence(),
        diagnostics=log.active(),
        posix=os.name != "nt",
        greeting=_persona_greeting,
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


def build_list_jobs() -> ListJobsUseCase:
    """Build the ListJobsUseCase use case wired to the filesystem store.

    Returns:
        A ready-to-run ListJobsUseCase.
    """
    return ListJobsService(store=SqliteSessionStoreAdapter(_ledger()))


def build_list_sessions() -> ListSessionsUseCase:
    """Build the ListSessionsUseCase use case wired to the session and usage stores.

    Returns:
        A ready-to-run ListSessionsUseCase.
    """
    return ListSessionsService(
        store=SqliteSessionStoreAdapter(_ledger()),
        turns=SqlitePerTurnStoreAdapter(_ledger()),
        usage=SqliteUsageStoreAdapter(_ledger()),
    )


def build_delete_sessions() -> DeleteSessionsUseCase:
    """Build the DeleteSessionsUseCase use case wired to the stores and both purges.

    Returns:
        A ready-to-run DeleteSessionsUseCase.
    """
    return DeleteSessionsService(
        store=SqliteSessionStoreAdapter(_ledger()),
        turns=SqlitePerTurnStoreAdapter(_ledger()),
        usage=SqliteUsageStoreAdapter(_ledger()),
        ledger=SqliteLedgerPurgeAdapter(_ledger()),
        artifacts=_artifact_purge(),
        locks=_session_locks(),
        diagnostics=log.active(),
    )


def build_delete_jobs() -> DeleteJobsUseCase:
    """Build the DeleteJobsUseCase use case wired to the stores and both purges.

    The session store is the default ``work``-scoped one, so ``authoring`` jobs are
    unreachable here exactly as they are unreachable from ``gmlw jobs``.

    Returns:
        A ready-to-run DeleteJobsUseCase.
    """
    return DeleteJobsService(
        store=SqliteSessionStoreAdapter(_ledger()),
        turns=SqlitePerTurnStoreAdapter(_ledger()),
        usage=SqliteUsageStoreAdapter(_ledger()),
        ledger=SqliteLedgerPurgeAdapter(_ledger()),
        artifacts=_artifact_purge(),
        locks=_session_locks(),
        diagnostics=log.active(),
    )


def build_export_workflow() -> ExportWorkflowUseCase:
    """Build the ExportWorkflowUseCase use case wired to the zip archive under ~/.gmlw/exports.

    Returns:
        A ready-to-run ExportWorkflowUseCase.
    """
    return ExportWorkflowService(
        workflows=_workflow_source(InterceptorChain(())),
        archive=ZipWorkflowArchiveAdapter(paths.exports, lambda: datetime.now(UTC)),
    )


def build_import_workflow() -> ImportWorkflowUseCase:
    """Build the ImportWorkflowUseCase use case wired to the zip archive and the backup root.

    Returns:
        A ready-to-run ImportWorkflowUseCase.
    """
    return ImportWorkflowService(
        workflows=_workflow_source(InterceptorChain(())),
        archive=ZipWorkflowArchiveAdapter(paths.exports, lambda: datetime.now(UTC)),
        backups=FilesystemWorkflowBackupAdapter(paths.workflow_backups, lambda: datetime.now(UTC)),
    )


def build_list_workflow_catalog() -> ListWorkflowCatalogUseCase:
    """Build the ListWorkflowCatalogUseCase use case wired to the filesystem workflow source.

    Returns:
        A ready-to-run ListWorkflowCatalogUseCase.
    """
    return ListWorkflowCatalogService(workflows=_workflow_source(InterceptorChain(())))


def build_list_drafts() -> ListDraftsUseCase:
    """Build the ListDraftsUseCase use case wired to the filesystem workflow source.

    Returns:
        A ready-to-run ListDraftsUseCase.
    """
    return ListDraftsService(workflows=_workflow_source(InterceptorChain(())))


def build_list_workflows() -> ListWorkflowsUseCase:
    """Build the ListWorkflowsUseCase use case wired to the filesystem workflow source.

    Returns:
        A ready-to-run ListWorkflowsUseCase.
    """
    return ListWorkflowsService(workflows=_workflow_source(InterceptorChain(())))


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


def build_set_credential() -> SetCredentialUseCase:
    """Build the SetCredentialUseCase use case wired to the filesystem credentials store.

    Returns:
        A ready-to-run SetCredentialUseCase.
    """
    return SetCredentialService(
        store=FilesystemCredentialsStoreAdapter(paths.credentials),
        prompt=TtySecretPromptAdapter(),
    )


def build_check_store_contract() -> CheckStoreContractUseCase:
    """Build the CheckStoreContractUseCase use case wired to the shipped migrations.

    Returns:
        A ready-to-run CheckStoreContractUseCase.
    """
    return CheckStoreContractService(migration=build_store_migration())


def build_describe_build() -> DescribeBuildUseCase:
    """Build the DescribeBuildUseCase use case wired to the build stamp.

    Returns:
        A ready-to-run DescribeBuildUseCase.
    """
    return DescribeBuildService(build_info=ModuleBuildInfoAdapter())


def build_check_launch_location() -> CheckLaunchLocationUseCase:
    """Build the CheckLaunchLocationUseCase use case wired to the filesystem.

    Returns:
        A ready-to-run CheckLaunchLocationUseCase.
    """
    return CheckLaunchLocationService(folders=FilesystemWorkingFolderAdapter())


def build_bootstrap() -> BootstrapUseCase:
    """Build the BootstrapUseCase use case wired to the filesystem layout seeder.

    Returns:
        A ready-to-run BootstrapUseCase.
    """
    return BootstrapService(seeder=FilesystemLayoutSeederAdapter(paths.home))


def build_config_commands() -> ConfigCommandsUseCase:
    """Build the ConfigCommandsUseCase use case wired to the tomlkit config writer.

    Returns:
        A ready-to-run ConfigCommandsUseCase, writing to ``~/.gmlw/config.toml``.
    """
    return UpdateConfigService(
        writer=TomlkitConfigWriterAdapter(config.config_path),
        settings=TomlSettingsCatalogAdapter(config.config_path),
    )


def build_application_settings() -> ApplicationSettingsUseCase:
    """Build the ApplicationSettingsUseCase use case over the user's configured settings.

    Returns:
        A ready-to-ask ApplicationSettingsUseCase.
    """
    return ReadApplicationSettingsService(TomlRuntimeConfigAdapter())


def build_list_supported_clients() -> ListSupportedClientsUseCase:
    """Build the ListSupportedClientsUseCase use case over the packaged catalogue.

    Returns:
        A ready-to-run ListSupportedClientsUseCase.
    """
    return ListSupportedClientsService(TomlClientCatalogAdapter())


def build_create_axis() -> CreateAxisUseCase:
    """Build the CreateAxisUseCase use case wired to the filesystem catalog and config writer.

    Returns:
        A ready-to-run CreateAxisUseCase, creating folders under ``~/.gmlw`` and, when asked,
        pointing ``profile.default_<kind>`` at the new slug in ``config.toml``.
    """
    return CreateAxisService(
        catalog=FilesystemAxisCatalogAdapter(paths.home),
        writer=TomlkitConfigWriterAdapter(config.config_path),
        clock=lambda: datetime.now(UTC).astimezone(),
    )


def build_axis_catalog() -> AxisCatalogPort:
    """Build the role/environment catalog reader over ``~/.gmlw``.

    Returns:
        A ready-to-use :class:`AxisCatalogPort` for listing the axis slug-folders.
    """
    return FilesystemAxisCatalogAdapter(paths.home)


def build_list_rules() -> ListRulesUseCase:
    """Build the ListRulesUseCase use case for the TUI's Rules browser.

    Returns:
        A ready-to-run ListRulesUseCase over the environment and role rule folders.
    """
    return ListRulesService(
        catalog=FilesystemRuleCatalogAdapter(paths.home, FilesystemAxisCatalogAdapter(paths.home))
    )


def build_migrate_layout() -> MigrateLayoutUseCase:
    """Build the MigrateLayoutUseCase use case: wrap the old layout into the active environment.

    Reads the persisted ``default_environment`` at call time, so it runs correctly after
    init has written it (and idempotently on every later run).

    Returns:
        A ready-to-run MigrateLayoutUseCase.
    """
    return MigrateLayoutService(
        FilesystemLayoutMigratorAdapter(paths.home),
        environment=config.default_environment,
    )


def build_migrate_slugs() -> MigrateSlugsUseCase:
    """Build the MigrateSlugsUseCase use case: rename legacy raw-named role/environment folders.

    Idempotent — a no-op once every folder is already a clean slug.

    Returns:
        A ready-to-run MigrateSlugsUseCase.
    """
    return MigrateSlugsService(FilesystemSlugMigratorAdapter(paths.home))


def build_save_init_answers() -> SaveInitAnswersUseCase:
    """Build the SaveInitAnswersUseCase use case wired to the seeder.

    All that is left of the old init use case. The interview itself is the terminal's:
    it asks the queries what is on offer, converses, and hands the answers back here.

    Returns:
        A ready-to-run SaveInitAnswersUseCase.
    """
    return SaveInitAnswersService(
        seeder=FilesystemLayoutSeederAdapter(paths.home),
        detector=PathClientDetectorAdapter(),
        version=__version__,
    )


def seed_localizer() -> MessageSource:
    """The catalogue the language question itself is asked in.

    Resolves from ``[language] code`` if a prior run set it, else ``$LANG``. The language
    menu offers each language under its own name, so this only affects the words around
    it -- and the terminal rebuilds the catalogue in the chosen language straight after.

    Returns:
        A message source for the seeded language.
    """
    return load_localizer(resolve_language(config.language() or os.environ.get("LANG")))


def default_user_name() -> str:
    """The account name, used when the user gives none.

    Asked here rather than in the terminal: reading the operating system is acquiring,
    and an inbound adapter parses its own channel and nothing else.
    """
    return OsSystemInfoAdapter().username()


def platform_name() -> str:
    """The OS name, so an install command is the right one for this machine."""
    return OsSystemInfoAdapter().platform_name()


def seed_language() -> str:
    """The language code the interview starts in (before the user chooses)."""
    return resolve_language(config.language() or os.environ.get("LANG"))


def build_localizer() -> MessageSource:
    """Build the localiser for the language the wrapper speaks to the user.

    Prefers the init-chosen ``[language] code``; falls back to ``$LANG`` (English when
    unset or unsupported) until init has run.

    Returns:
        A ready-to-use localiser.
    """
    return load_localizer(resolve_language(config.language() or os.environ.get("LANG")))


def build_check_client_ready() -> CheckClientReadyUseCase:
    """Build the CheckClientReadyUseCase use case wired to config overrides and PATH detection.

    Returns:
        A ready-to-run CheckClientReadyUseCase.
    """
    return CheckClientReadyService(
        overrides=config.caller_overrides(),
        detector=PathClientDetectorAdapter(),
        catalog=TomlClientCatalogAdapter(),
        system=OsSystemInfoAdapter(),
    )


def build_export_usage() -> ExportUsageUseCase:
    """Build the ExportUsageUseCase use case wired to the filesystem usage store.

    Returns:
        A ready-to-run ExportUsageUseCase.
    """
    return ExportUsageService(
        usage=SqliteUsageStoreAdapter(_ledger()),
        turns=SqlitePerTurnStoreAdapter(_ledger()),
    )


def build_save_usage_report() -> SaveUsageReportUseCase:
    """Build the SaveUsageReportUseCase use case: the report source plus the filesystem JSON writer.

    Returns:
        A ready-to-run SaveUsageReportUseCase writing to ``~/.gmlw/exports``.
    """
    return SaveUsageReportService(
        export=build_export_usage(),
        exporter=FilesystemReportExporterAdapter(
            paths.exports, clock=lambda: datetime.now(UTC).astimezone()
        ),
    )


def build_compose_statusline() -> ComposeStatuslineUseCase:
    """Build the ComposeStatuslineUseCase use case.

    It takes no client: the status line is invoked by a client the wrapper launched, and
    that launch already announced which one it was. The use case reads that announcement
    and resolves its own parser, so nothing upstream has to know either.

    Returns:
        A ready-to-run ComposeStatuslineUseCase.
    """
    return ComposeStatuslineService(
        parsers=CataloguedStatusParsersAdapter(paths.cursor_plan),
        handoff=EnvironmentRunHandoffAdapter(),
        usage=SqliteUsageStoreAdapter(_ledger()),
        workspace=LocalGitWorkspaceInspectorAdapter(),
        turns=SqlitePerTurnStoreAdapter(_ledger()),
        diagnostics=log.active(),
    )


def build_new_workflow() -> NewWorkflowUseCase:
    """Build the NewWorkflowUseCase use case wired to its outbound adapters.

    Returns:
        A ready-to-run NewWorkflowUseCase.
    """
    interceptors = _interceptor_chain()
    sessions = SqliteSessionStoreAdapter(_ledger())
    return NewWorkflowService(
        workflows=_workflow_source(interceptors),
        store=sessions,
        callers=DefaultCliCallerProviderAdapter(
            config.caller_overrides(),
            metering=SqlitePerTurnStoreAdapter(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
            sessions=sessions,
        ),
        uuid_factory=lambda: str(uuid.uuid4()),
        launch=_launch_sequence(),
    )


def build_edit_workflow() -> EditWorkflowUseCase:
    """Build the EditWorkflowUseCase use case wired to its outbound adapters.

    Returns:
        A ready-to-run EditWorkflowUseCase.
    """
    interceptors = _interceptor_chain()
    sessions = SqliteSessionStoreAdapter(_ledger())
    return EditWorkflowService(
        workflows=_workflow_source(interceptors),
        store=sessions,
        callers=DefaultCliCallerProviderAdapter(
            config.caller_overrides(),
            metering=SqlitePerTurnStoreAdapter(_ledger()),
            transcript=_transcript(),
            interceptors=interceptors,
            plugins=build_plugin_source(),
            sessions=sessions,
        ),
        uuid_factory=lambda: str(uuid.uuid4()),
        launch=_launch_sequence(),
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
        return NullDiagnosticsAdapter()
    level = os.environ.get("GMLW_LOG_LEVEL") or config.log_level(path)
    sinks: list[DiagnosticsPort] = []
    if config.log_to_file(path):
        sinks.append(
            RollingFileDiagnosticsAdapter(
                paths.log_file,
                level=level,
                max_bytes=config.log_max_bytes(path),
                backup_count=config.log_backup_count(path),
            )
        )
    if to_stderr:
        sinks.append(StderrDiagnosticsAdapter(level=level))
    if not sinks:
        return NullDiagnosticsAdapter()
    return sinks[0] if len(sinks) == 1 else TeeDiagnosticsAdapter(*sinks)


def build_list_available_languages() -> ListAvailableLanguagesUseCase:
    """Build the ListAvailableLanguagesUseCase use case over the packaged catalogues.

    Returns:
        A ready-to-ask ListAvailableLanguagesUseCase.
    """
    return ListAvailableLanguagesService(JsonCatalogLanguageCatalogAdapter())


def build_list_authoring_modes() -> ListAuthoringModesUseCase:
    """Build the ListAuthoringModesUseCase use case.

    Returns:
        A ready-to-ask ListAuthoringModesUseCase.
    """
    return ListAuthoringModesService()


def build_list_axis_examples() -> ListAxisExamplesUseCase:
    """Build the ListAxisExamplesUseCase use case over the offered role/environment examples.

    Returns:
        A ready-to-ask ListAxisExamplesUseCase.
    """
    return ListAxisExamplesService()
