-- Make the relationships real: jobs <- sessions <- turns/costs (version 6).
--
-- Until now every relationship in this schema was a loose name. ``PRAGMA foreign_keys=ON``
-- has been set on every connection since the ledger existed and enforced nothing, because
-- no table declared a reference for it to enforce. A turn could name a session that did
-- not exist, and a row could name a job that contradicted the job of the session it also
-- named -- two parents, free to disagree.
--
-- ``sessions.session_id`` is unique across the whole table, so a session id already
-- determines its job. The ``job`` column that ``turns`` and ``session_costs`` also carried
-- was a denormalised copy kept only to save a join, and it is dropped here: it is the
-- column that made the contradiction expressible.
--
-- ``ON DELETE CASCADE`` states in the schema the deletion order the purge adapter used to
-- spell out by hand. Removing a job now takes its sessions, their turns and their costs
-- with it; removing a session takes its turns and its cost and leaves the job standing,
-- which is the behaviour that was already intended.
--
-- SQLite cannot add a constraint to an existing table, so each table is rebuilt: create
-- the replacement, copy the rows, drop the original, rename. The runner has already set
-- ``PRAGMA foreign_keys = OFF`` for exactly this, and the whole file commits as one
-- transaction. Indexes live on the table they index, so each one is recreated below.
--
-- Order matters: parents before children, so a child's copy never references a table that
-- has not been rebuilt yet.
--
-- The runner owns the transaction: this file must not BEGIN or COMMIT.

-- sessions: its job becomes a reference to the jobs table.
CREATE TABLE sessions_new (
    id         INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    job        TEXT NOT NULL REFERENCES jobs(job) ON DELETE CASCADE,
    client     TEXT NOT NULL,
    uuid       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    cwd        TEXT,
    resumable  INTEGER NOT NULL DEFAULT 1
);

INSERT INTO sessions_new (id, session_id, job, client, uuid, created_at, cwd, resumable)
SELECT id, session_id, job, client, uuid, created_at, cwd, resumable FROM sessions;

DROP TABLE sessions;
ALTER TABLE sessions_new RENAME TO sessions;
CREATE INDEX idx_sessions_job ON sessions(job);

-- turns: keyed to its session alone; the job is reached through it.
CREATE TABLE turns_new (
    id                    INTEGER PRIMARY KEY,
    session_id            TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    turn_id               TEXT,
    input_tokens          INTEGER NOT NULL,
    output_tokens         INTEGER NOT NULL,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
    cost_usd              REAL,
    model                 TEXT,
    timestamp             REAL NOT NULL DEFAULT 0,
    duration_s            REAL NOT NULL DEFAULT 0
);

INSERT INTO turns_new (id, session_id, turn_id, input_tokens, output_tokens,
                       cache_creation_tokens, cache_read_tokens, cost_usd, model,
                       timestamp, duration_s)
SELECT id, session_id, turn_id, input_tokens, output_tokens,
       cache_creation_tokens, cache_read_tokens, cost_usd, model,
       timestamp, duration_s
FROM turns;

DROP TABLE turns;
ALTER TABLE turns_new RENAME TO turns;
-- Replaces idx_turns_job: the job is no longer here, and a child's reference column wants
-- its own index -- SQLite indexes the parent's key automatically but never the child's,
-- and a cascading delete looks the child up on every parent row removed.
CREATE INDEX idx_turns_session ON turns(session_id);

-- session_costs: one row per session, and now provably per *existing* session.
CREATE TABLE session_costs_new (
    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
    cost_usd   REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO session_costs_new (session_id, cost_usd, updated_at)
SELECT session_id, cost_usd, updated_at FROM session_costs;

DROP TABLE session_costs;
ALTER TABLE session_costs_new RENAME TO session_costs;
-- idx_session_costs_job is not recreated: the column it indexed is gone, and the primary
-- key already covers the only lookup left.
