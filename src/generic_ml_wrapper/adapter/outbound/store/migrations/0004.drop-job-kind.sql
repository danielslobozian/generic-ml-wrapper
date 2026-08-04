-- Remove the dead ``kind`` column from ``jobs`` (version 4).
--
-- SQLite cannot alter a column away in a form that also lets constraints be added
-- later, so this is the documented table-rebuild: create the replacement, copy the
-- rows, drop the original, rename. The runner has already set ``PRAGMA foreign_keys =
-- OFF`` for exactly this, and the whole file commits as one transaction.
--
-- Indexes on ``jobs`` would have to be recreated here; it has none.

CREATE TABLE jobs_new (
    job        TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO jobs_new (job, created_at) SELECT job, created_at FROM jobs;

DROP TABLE jobs;

ALTER TABLE jobs_new RENAME TO jobs;
