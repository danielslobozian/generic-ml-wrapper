# Troubleshooting

Recovery and diagnosis for `gmlw` (v0.2.0). Most "problems" below are by-design
behaviour — the answers say so where that's the case. When something is genuinely
misconfigured, `gmlw` prefers to fail loudly; turning up logging is usually the
fastest way to see why.

## Why is Cursor showing no token cost?

By design. Cursor is **not metered** by the OSS wrapper — its usage doesn't run over
an interceptable API, so there is no relay to record tokens or cost against. This is
not a bug and nothing is missing from your ledger. Cursor still gets a status line and
resume support; it just never contributes a cost. See [CLIENTS.md](CLIENTS.md) for the
per-client capability matrix.

## Why does Cursor's status line vanish when I paste a file path?

Upstream Cursor behaviour, not a `gmlw` bug. `cursor-agent` treats `/` as a
slash-command trigger **even mid-input**, so a pasted file path (which contains `/`)
makes Cursor's slash UI take over the status-line row — and it stays hidden until you
delete the text containing the `/`. It is independent of what `gmlw` renders into the
status line, and the wrapper has no hook into Cursor's input mode to prevent it. Remove
the `/` (or send/clear the input) and the status line comes back.

## Why can't this Codex session resume? Why can't Vibe?

Neither takes a session id at launch, so the wrapper cannot name the session up front the
way it does for **claude** and **cursor**. The difference is what happens next: Codex mints
its own id and announces it on the wire, so the relay binds it to the session on the first
metered turn — from there `--resume-latest` works. A codex session that never completed a
turn has no id, and one you deleted in codex itself is gone from its index; both are shown
as not resumable rather than reopened as a fresh, empty session wearing the old name.

Vibe exposes no stable client-side id at all, so every vibe run is a new session. See
[CLIENTS.md](CLIENTS.md).

## Why did a run launch unmetered?

Two possibilities:

1. **The client isn't metered.** Cursor is never metered (see above). Only claude,
   codex, and vibe run through the relay.
2. **The relay couldn't stand up.** For a metered client, if the local proxy failed to
   start, the run proceeds unmetered rather than blocking your work.

To find out which, raise the log level and re-run — relay startup issues are reported
there:

```
GMLW_LOG_LEVEL=debug gmlw start <job> --client <client>
```

or set `[logging] level = "debug"` in `~/.gmlw/config.toml`. See
[CONFIGURATION.md](CONFIGURATION.md).

## Where do I look when something goes wrong *during* a session?

`~/.gmlw/logs/gmlw.log`.

While a client is running it owns the terminal, so the wrapper cannot report anything
to the screen without corrupting the client's display — and anything it did write
would be painted over on the next redraw. Diagnostics for those commands (`start`,
`run`, `tui`, `workflow new/edit`) therefore go **only** to the log file:

```
tail -f ~/.gmlw/logs/gmlw.log
```

Caught failures are recorded there with their full traceback, so a relay or upstream
error that happened ten minutes ago is still there to read. The file rolls at 1 MiB
and keeps 5 backups; API keys, tokens and e-mail addresses are redacted as it is
written. Utility commands (`gmlw jobs`, `gmlw config list`, …) log to the file *and*
to stderr, since nothing else is using the screen.

## A Python traceback appeared over my client's UI

Fixed in 0.8.0. The metering relay had no error boundary, so a TLS error in a request
thread was printed as a raw traceback to a `stderr` shared with the client's TUI —
unreadable, uncopyable, and saved nowhere.

Now such a failure returns a clean `502` to the client (which retries), and the
traceback goes to `~/.gmlw/logs/gmlw.log`. If you still see one, it is a bug worth
reporting — please include the log file's tail.

## How are client status-line settings restored after exit or crash?

The wrapper snapshots your client status-line settings before launch and restores them
on exit — this covers `~/.claude/settings.json` and `~/.cursor/cli-config.json`. Writes
are atomic, so a crash mid-write can't leave a half-written file. Critically, the wrapper
**refuses to overwrite a settings file it cannot parse**: if your `settings.json` /
`cli-config.json` is malformed, the wrapper leaves it untouched rather than destroy it.
If your status line doesn't come back after a crash, check that file parses as valid
JSON.

## What do I delete to reset the ledger or config?

Everything lives under `~/.gmlw`:

- **Reset the ledger:** delete `~/.gmlw/ledger.db` (SQLite/WAL). All recorded jobs,
  sessions, turns, and costs go with it.
- **Reset config:** delete `~/.gmlw/config.toml` to fall back to built-in defaults.

The home dir and store are re-seeded on the next run, so deleting these is safe — you
just lose the recorded history. Note that a **schema change before 1.0 is a full store
reset** (`SCHEMA_VERSION = 1`), not a migration: expect to clear `ledger.db` after an
upgrade that bumps the schema.

## How do I diagnose a bad interceptor, plugin, or caller spec?

A configured-but-**unloadable** spec fails **loudly** — the wrapper won't silently
ignore a `[callers]` or `[[interceptors]]` entry it can't import. (An entry that is
simply absent is a silent no-op; only a present-but-broken one raises.) To see the
failure:

```
GMLW_LOG_LEVEL=debug gmlw start <job>
```

Then check the offending spec in `~/.gmlw/config.toml`:

- `[callers]` — `<client> = "module:Class"`, `"/path/to/file.py:Class"`, or a plugin id.
- `[[interceptors]]` — `target = "..."`, `spec = "module:Class"`.

Confirm the module path/file exists and the class name is spelled correctly. These specs
are **trusted code** — they import and run as you — so only configure specs you wrote or
trust. See [CONFIGURATION.md](CONFIGURATION.md).

## What is safe to back up or move?

- **Transcripts and contexts** — `~/.gmlw/transcripts/` and `~/.gmlw/contexts/` are
  self-contained and portable; copy or move them freely.
- **`credentials.toml`** is `0600` secrets (per-workflow credentials injected into the
  child client). Treat it as sensitive; it never leaves your machine on its own.
- The **whole `~/.gmlw`** is created owner-only (`0700`). Keep any backup owner-only too.

Remember the transcripts folder, when the feature is enabled, holds full prompts and
responses at rest — see [../SECURITY.md](../SECURITY.md).

## How do I turn up logging?

Two equivalent knobs, `warning` by default:

- Config: set `[logging] level = "debug"` in `~/.gmlw/config.toml`.
- Env: `GMLW_LOG_LEVEL=debug` for a single run.

Levels are `debug | info | warning | error`. Debug is the right setting when diagnosing
any of the issues above. See [CONFIGURATION.md](CONFIGURATION.md).
