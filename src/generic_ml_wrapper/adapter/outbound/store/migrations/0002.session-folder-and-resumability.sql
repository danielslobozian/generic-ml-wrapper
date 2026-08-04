-- Record where a session ran, and whether its client could reopen it (version 2).
--
-- Without the folder an interrupted session had nowhere to return to: a cwd-scoped
-- client resumes in the directory it was launched from, and we had not kept it.
-- ``resumable`` snapshots what the client could do at the time, rather than asking a
-- catalogue that may since have changed.

ALTER TABLE sessions ADD COLUMN cwd TEXT;
ALTER TABLE sessions ADD COLUMN resumable INTEGER NOT NULL DEFAULT 1;

-- Backfill from the client that made the session: codex and vibe minted their own ids
-- and could not be targeted, so those sessions were never resumable. Everything else
-- keeps the default.
UPDATE sessions SET resumable = 0 WHERE client IN ('codex', 'vibe');
