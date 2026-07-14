# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A context compressor interceptor that compresses through generic-ml-cache."""

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

from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.common import config, paths
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


class CompressorInterceptor(InterceptorPort):
    """Compress a context section through the generic-ml-cache record/replay cache.

    Runs the configured model (default gpt-5.4 at low effort via the cursor adapter)
    with the user's compression prompt, keyed and cached by content — so compressing
    the same context replays for free and returns an identical result. Off until
    ``[compress] prompt`` names a prompt file; non-destructive — any failure leaves
    the text uncompressed.
    """

    def intercept(self, text: str, target: str) -> str:  # noqa: ARG002  (target-agnostic)
        """Return the compressed text, or the input unchanged when off or on failure.

        Args:
            text: The section text to compress.
            target: The target it is running for (unused; a compressor is target-agnostic).

        Returns:
            The compressed text, or ``text`` unchanged.
        """
        settings = config.compress()
        if settings.prompt is None:
            return text  # compression off until [compress] prompt is set
        try:
            prompt = Path(settings.prompt).read_text(encoding="utf-8")
        except OSError as error:
            log.warning(f"cannot read compress prompt {settings.prompt!r} ({error}); skipping")
            return text
        try:
            execution = self._compress(text, prompt, settings)
        except Exception as error:  # noqa: BLE001  (a compile must never die on the cache/LLM)
            log.warning(f"compression failed ({error}); leaving context uncompressed")
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
