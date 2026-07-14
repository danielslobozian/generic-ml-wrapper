# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``TranscriptPort``: the self-contained per-call in/out/usage trio.

Each metered call writes three files under ``<root>/<job>/<session>/``::

    call_001.in.json     the request body forwarded upstream
    call_001.out.sse     the raw response body
    call_001.usage.json  tokens, cost, model, and timing

The folder is self-identifying, so it can be copied out and analysed with no
knowledge of the ledger. ``usage.json`` deliberately duplicates the metering row --
that is what makes the folder portable.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.transcript import TranscriptCall, TranscriptPort

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage


class FilesystemTranscriptStore(TranscriptPort):
    """Persist each call's in/out/usage trio under a per-session folder."""

    def __init__(self, root: Path) -> None:
        """Bind the store to its transcript root.

        Args:
            root: The directory under which ``<job>/<session>/`` folders are written.
        """
        self._root = root

    def record(self, call: TranscriptCall) -> None:
        """Write the call's request, response, and usage as the three trio files."""
        directory = self._root / call.job / call.session
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"call_{call.call_seq:03d}"
        (directory / f"{stem}.in.json").write_bytes(call.request)
        (directory / f"{stem}.out.sse").write_bytes(call.response)
        (directory / f"{stem}.usage.json").write_text(
            json.dumps(_usage_dict(call.usage), indent=2), encoding="utf-8"
        )


def _usage_dict(usage: TurnUsage | None) -> dict[str, object]:
    if usage is None:
        return {}
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_tokens": usage.cache_creation_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cost_usd": usage.cost_usd,
        "model": usage.model,
        "timestamp": usage.timestamp,
        "duration_s": usage.duration_s,
        "turn_id": usage.turn_id,
    }
