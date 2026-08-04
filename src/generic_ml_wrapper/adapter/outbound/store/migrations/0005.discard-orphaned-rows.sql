-- Remove rows whose parent is gone, before the parents become enforceable (version 5).
--
-- Nothing has ever stopped a row naming a session or a job that no longer exists: the
-- next migration turns those names into real references, and SQLite will not enforce a
-- constraint against rows that predate it, so an orphan left here would sit undetected
-- for the rest of the store's life.
--
-- Deliberately its own file rather than part of the rebuild. The runner reports how many
-- rows a migration changed, and that number is only meaningful -- "this many orphans were
-- discarded" -- while the file does nothing else. Folded into the rebuild it would be
-- swamped by the row copy.
--
-- Discarding is the decided policy: refusing to start would leave a user with no remedy
-- but hand-written SQL, and inventing the missing parents would put sessions that never
-- happened into the listing.
--
-- Parents first: a session whose job is gone is itself discarded here, and the turns
-- below it only become orphans once it has been. Sweeping the children first would leave
-- them attached to a session this same file is about to remove.
--
-- The runner owns the transaction: this file must not BEGIN or COMMIT.

DELETE FROM sessions
WHERE job NOT IN (SELECT job FROM jobs);

DELETE FROM turns
WHERE session_id NOT IN (SELECT session_id FROM sessions);

DELETE FROM session_costs
WHERE session_id NOT IN (SELECT session_id FROM sessions);
