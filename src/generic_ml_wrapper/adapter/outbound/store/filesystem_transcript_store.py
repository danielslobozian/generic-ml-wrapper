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

The numbers run on across runs: a resumed session's first call takes the number after
the last one already kept, in its folder or in its archives, so it never writes over a
call an earlier run recorded.
"""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.filesystem_transcript_archive import (
    next_call_number,
)
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
        # Per session: the calls already kept when this run first recorded one. The relay
        # numbers its own calls from 1, and the server is threaded, hence the lock.
        self._kept: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def record(self, call: TranscriptCall) -> None:
        """Write the call's request, response, and usage as the three trio files."""
        directory = self._root / call.job / call.session
        with self._lock:
            key = (call.job, call.session)
            if key not in self._kept:
                self._kept[key] = next_call_number(directory.parent, call.session) - 1
            number = self._kept[key] + call.call_seq
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"call_{number:03d}"
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
        "execution_tags": usage.execution_tags.as_dict(),
    }
