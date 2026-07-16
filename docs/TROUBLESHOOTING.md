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

## Why can't Codex or Vibe resume?

Codex and Vibe don't expose a stable client-side session id, so the wrapper has nothing
to reattach to on the next launch. `--resume-latest` therefore only works for **claude**
and **cursor**. For codex/vibe, start a fresh session each time. See
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
