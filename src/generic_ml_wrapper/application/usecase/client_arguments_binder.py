# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Attaching a run's passthrough launch arguments, for both the start and resume paths."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from generic_ml_wrapper.application.domain.model.client_arguments import ClientArguments
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort


class ClientArgumentsBinder:
    """Attach the passthrough launch arguments a run should carry."""

    def __init__(
        self,
        configured: Callable[[str], str],
        posix: bool,
        diagnostics: DiagnosticsPort,
    ) -> None:
        """Wire the binder to its collaborators.

        Args:
            configured: Returns the configured passthrough arguments for a client.
            posix: Whether launch arguments split by POSIX rules (false on Windows).
            diagnostics: Where an unparseable argument string is reported.
        """
        self._configured = configured
        self._posix = posix
        self._diagnostics = diagnostics

    def bind(self, run: RunContext, override: str | None) -> RunContext:
        """Attach the arguments for this run's client.

        An explicit override replaces the configured value outright rather than adding to
        it: the flag names the arguments for *this* launch, and a user who wants the
        configured ones as well can type them.

        Args:
            run: The run to attach to. Its client is what the lookup is keyed on — on a
                resume that is the session's own, so a resumed codex session never picks
                up arguments configured for claude.
            override: The arguments for this launch, or ``None`` to use the configured
                value.

        Returns:
            The run, carrying the parsed arguments when there are any.
        """
        text = override if override is not None else self._configured(run.client)
        arguments = ClientArguments.parse(text, posix=self._posix)
        if arguments.unparseable:
            self._diagnostics.warning(
                f"could not parse the client arguments {text!r} "
                f"({arguments.unparseable}); launching without them",
                key="log.client_args_unparseable",
            )
        return run if not arguments.tokens else replace(run, client_args=arguments.tokens)
