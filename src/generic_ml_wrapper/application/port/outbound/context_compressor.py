# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for compressing a single context source."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ContextCompressorPort(ABC):
    """Compress one context source through its data-typed compression prompt."""

    @abstractmethod
    def compress(self, text: str, *, source_key: str, kind: str | None) -> str:
        """Return the compressed source text, or the input unchanged.

        Non-destructive: when no prompt resolves for the source (by key, then by
        kind) or compression fails, the original ``text`` is returned so a compile
        never loses context or dies on the cache/LLM.

        Args:
            text: The source text to compress.
            source_key: The source's config key (e.g. ``"me.user"``), tried first
                for a prompt override.
            kind: The source's default compressor kind, tried next, or ``None``.

        Returns:
            The compressed text, or ``text`` unchanged.
        """
