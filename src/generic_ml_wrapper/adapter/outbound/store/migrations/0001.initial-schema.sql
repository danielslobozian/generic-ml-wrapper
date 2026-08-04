-- The ledger as it first shipped (schema version 1).
--
-- Reconstructed verbatim from the original create-from-final-state schema so that a
-- database created today runs the same lineage an existing one did, and the two end in
-- the same shape. Later files evolve it; nothing here is edited after the fact.
--
-- The runner owns the transaction: this file must not BEGIN or COMMIT.

CREATE TABLE jobs (
    job        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL DEFAULT 'work',   -- 'work' | 'authoring'; dropped in 0004
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sessions (
    id         INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,           -- <job>_NNN
    job        TEXT NOT NULL,
    client     TEXT NOT NULL,
    uuid       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_sessions_job ON sessions(job);

CREATE TABLE turns (
    id                    INTEGER PRIMARY KEY,
    job                   TEXT NOT NULL,
    session_id            TEXT NOT NULL,
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
CREATE INDEX idx_turns_job ON turns(job);

CREATE TABLE session_costs (
    session_id TEXT PRIMARY KEY,
    job        TEXT NOT NULL,
    cost_usd   REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_session_costs_job ON session_costs(job);
