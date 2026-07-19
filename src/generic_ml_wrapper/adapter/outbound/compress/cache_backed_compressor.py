# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A typed context compressor that compresses through generic-ml-cache."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from generic_ml_cache_bootstrap.application import build_application_api
from generic_ml_cache_core.application.domain.model.execution.artifact import ArtifactType
from generic_ml_cache_core.application.domain.model.execution.execution_kind import ExecutionKind
from generic_ml_cache_core.application.domain.model.run.cache_mode import CacheMode
from generic_ml_cache_core.application.port.inbound.run_ml_execution import (
    run_ml_execution_command as _run_cmd,
)
from generic_ml_cache_core.application.usecase.select_adapter_for_execution_service import (
    SelectAdapterForExecutionService,
)

from generic_ml_wrapper.application.port.outbound.context_compressor import ContextCompressorPort
from generic_ml_wrapper.common import config, i18n, paths
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from generic_ml_cache_core.application.domain.model.execution.ml_execution import MlExecution
    from generic_ml_cache_core.application.port.outbound.adapter_catalog_port import (
        AdapterCatalogPort,
    )
    from generic_ml_cache_core.application.port.outbound.adapter_resolver_port import (
        AdapterResolverPort,
    )
    from generic_ml_cache_core.application.port.outbound.registered_adapter_port import (
        RegisteredAdapterPort,
    )


class CacheBackedContextCompressor(ContextCompressorPort):
    """Compress a source through the generic-ml-cache record/replay cache.

    The prompt is chosen per source — a key-level override, else the source's kind
    (see the config's ``[compress.prompts]``) — so each data shape gets its own
    compressor. Runs the configured model (default gpt-5.4 at low effort via cursor),
    keyed and cached by content, so compressing the same source replays for free.
    Non-destructive: no prompt, an unreadable prompt, or any failure returns the text
    unchanged.
    """

    def compress(self, text: str, *, source_key: str, kind: str | None) -> str:
        """Return the compressed source text, or the input unchanged.

        Args:
            text: The source text to compress.
            source_key: The source's config key, tried first for a prompt override.
            kind: The source's default compressor kind, tried next, or ``None``.

        Returns:
            The compressed text, or ``text`` unchanged.
        """
        settings = config.compress()
        prompt_path = settings.prompt_for(source_key, kind)
        if prompt_path is None:
            return text  # no prompt resolves for this source -> leave it verbatim
        try:
            prompt = Path(prompt_path).read_text(encoding="utf-8")
        except OSError as error:
            log.warning(
                i18n.t("log.compress_prompt_unreadable", path=repr(prompt_path), error=error)
            )
            return text
        try:
            execution = self._compress(text, prompt, settings)
        except Exception as error:  # noqa: BLE001  (a compile must never die on the cache/LLM)
            log.warning(i18n.t("log.compress_failed", source=repr(source_key), error=error))
            return text
        return _stdout(execution) or text

    def _compress(  # pragma: no cover  (real cache/LLM round-trip; verified by a live run)
        self, context: str, prompt: str, settings: config.CompressSettings
    ) -> MlExecution:
        command = _run_cmd.RunMlExecutionCommand(
            execution_kind=ExecutionKind.LOCAL_MANAGED,
            client=settings.adapter,
            model=settings.model,
            effort=settings.effort,
            context=context,
            prompt=prompt,
            cache_mode=CacheMode.CACHE,
        )

        def runners(
            catalog: AdapterCatalogPort, resolver: AdapterResolverPort
        ) -> dict[str, RegisteredAdapterPort]:
            descriptor = SelectAdapterForExecutionService(catalog).select(
                settings.adapter, ExecutionKind.LOCAL_MANAGED
            )
            client = resolver.resolve_local_client(descriptor.adapter_id)
            return {settings.adapter: cast("RegisteredAdapterPort", client)}

        paths.COMPRESS_CACHE.mkdir(parents=True, exist_ok=True)
        api = build_application_api(paths.COMPRESS_CACHE, runners)
        return api.run_ml.execute(command)


def _stdout(execution: MlExecution) -> str | None:
    """Return the STDOUT artifact's text, or ``None`` on failure or if absent."""
    if execution.failure is not None:
        return None
    for artifact in execution.artifacts:
        if artifact.artifact_type is ArtifactType.STDOUT and artifact.content is not None:
            return artifact.content.decode(artifact.encoding or "utf-8")
    return None
