# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``JobTagStorePort``: the ``job_tags`` table of ``ledger.db``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.job_tag_store import JobTagStorePort

if TYPE_CHECKING:
    from collections.abc import Iterable

    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqliteJobTagStore(JobTagStorePort):
    """One row per (job, tag); the pair is the primary key, so a tag is held once."""

    def __init__(self, ledger: Ledger) -> None:
        """Bind the store to the ledger database.

        Args:
            ledger: The ledger whose ``job_tags`` table this reads and writes.
        """
        self._ledger = ledger

    def tags_by_job(self) -> dict[str, tuple[str, ...]]:
        """Return every tagged job's tags, each sorted."""
        with self._ledger.connect() as connection:
            rows = connection.execute("SELECT job, tag FROM job_tags ORDER BY job, tag").fetchall()
        tags: dict[str, list[str]] = {}
        for row in rows:
            tags.setdefault(row["job"], []).append(row["tag"])
        return {job: tuple(names) for job, names in tags.items()}

    def add(self, job: str, tags: Iterable[str]) -> None:
        """Put ``tags`` on ``job``; one already there is left as it is."""
        with self._ledger.connect() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO job_tags (job, tag) VALUES (?, ?)",
                [(job, tag) for tag in tags],
            )

    def remove(self, job: str, tags: Iterable[str]) -> None:
        """Take ``tags`` off ``job``."""
        with self._ledger.connect() as connection:
            connection.executemany(
                "DELETE FROM job_tags WHERE job = ? AND tag = ?",
                [(job, tag) for tag in tags],
            )
