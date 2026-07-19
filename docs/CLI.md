# CLI reference

Complete command reference for the `gmlw` console script (generic-ml-wrapper v0.2.0).
This page documents exactly what `build_parser()` exposes — every command, positional,
and flag. For deeper behaviour, follow the cross-links to [CONFIGURATION.md](CONFIGURATION.md),
[WORKFLOWS.md](WORKFLOWS.md), and [CLIENTS.md](CLIENTS.md).

## Synopsis

```
gmlw init                                # forced first-run setup (auto-runs when needed)
gmlw <job>                              # shorthand for: gmlw start <job>
gmlw start [job] [--client X] [--resume-latest] [--workflow|-w NAME]
gmlw jobs [--json]
gmlw sessions <job> [--json]
gmlw export <job> [--json]
gmlw statusline                          # called by the client, not by hand
gmlw workflow new <name> [--client X]
gmlw workflow list [--json]
gmlw persona list [--json]
gmlw plugins list [--json]
gmlw creds set <workflow> <ENV_VAR_NAME>
gmlw config list [--json]
gmlw config get <key> [--json]
gmlw config set <key> <value>
```

`--json` is accepted by the read commands only: `jobs`, `sessions`, `export`,
`workflow list`, `persona list`, and `plugins list`. It prints pretty-printed JSON
instead of the human-readable text.

### Implicit `start`

A first argument that is not a known command and does not begin with `-` is treated
as a job name: `gmlw myjob` is rewritten to `gmlw start myjob` (git-style). A recognized
subcommand or a leading flag is left untouched.

### Incomplete sub-commands

`workflow`, `persona`, `plugins`, and `creds` do their real work in a sub-action.
Invoked without one (e.g. `gmlw workflow`), the command re-parses itself as `-h` and
prints its own help, then exits 0.

### Environment variables

- `GMLW_LOG_LEVEL` — overrides the configured `[logging] level` for the run
  (`debug|info|warning|error`; default `warning`). See [CONFIGURATION.md](CONFIGURATION.md).
- `GMLW_CLIENT`, `GMLW_JOB`, `GMLW_SESSION` — exported by the launching caller and read
  by `statusline`; you do not set these yourself.

---

## init

Run the forced first-run setup that shapes every session. `init` is both a command and
a **gate**: the first time you run *any* command on a new or pre-0.4.0 install, gmlw
funnels you through it before that command runs. Once it has run, a marker
(`[init] version` in `~/.gmlw/config.toml`) records it, and the gate stays out of the way.

```
gmlw init
```

The interview captures, in order — each with a sensible default, so a non-interactive
run completes without blocking:

1. **language** — which language gmlw speaks *to you* (`en` | `fr`); it does not force the
   companion's language. Seeded from `$LANG`.
2. **name** — what the companion calls you (defaults to your OS user).
3. **role** — the functional hat you wear (a lens over *you*), e.g. `engineer`, `qa`.
4. **environment** — where the work happens, e.g. `work`, a personal project.
5. **persona** — the companion's voice (skippable; leaves the companion off).
6. **client** — the client to wrap by default; a lone installed one is taken silently,
   several prompt a choice, none leaves it unset.

On a **fresh** install a full `config.toml` is seeded with your choices. On a **legacy**
install (a pre-0.4.0 config already exists) only the `[init]` marker is appended — your
existing file is left untouched; migrating the older layout comes in a later release.

## start

Start or resume a session on a job.

```
gmlw start [job] [--client CLIENT] [--resume-latest] [--workflow|-w NAME]
```

- `job` (optional positional) — the job identifier. A job groups related sessions.
  With no job, `start` prints a friendly guide (not an argparse error) and exits 2:

  ```
  gmlw: start needs a job to work on.
    gmlw <job>          start (or resume) a session on <job>
    gmlw start <job>    the same, spelled out
  A job groups related sessions; list yours with:  gmlw jobs
  ```

- `--client CLIENT` — which client to wrap (`claude`, `cursor`, `codex`, `vibe`).
  Defaults to the configured default client, or `claude`. See [CLIENTS.md](CLIENTS.md).
- `--resume-latest` — resume the job's most recent session instead of starting a new one.
  Not every client supports resume; unsupported clients report an error.
- `--workflow NAME`, `-w NAME` — run a workflow on the job (list them with
  `gmlw workflow list`). See [WORKFLOWS.md](WORKFLOWS.md).

Before launching, `start` preflights the working directory and the client: a deleted
cwd or an uninstalled/unsupported client prints guidance and exits 2 rather than
crashing the child. If a companion persona is set, its host greeting is printed to
stderr just before the client takes over.

Example:

```
gmlw start billing-api --client claude -w tidy-review --resume-latest
```

## jobs

List the jobs with recorded activity. Authoring sessions (`workflow new`) are hidden.

```
gmlw jobs [--json]
```

- `--json` — output as JSON instead of text.

Example:

```
gmlw jobs
```

## sessions

List a job's sessions, oldest first.

```
gmlw sessions <job> [--json]
```

- `job` (positional, required) — the job identifier.
- `--json` — output as JSON instead of text.

Example:

```
gmlw sessions billing-api
```

## export

Report a job's recorded usage: per-turn tokens and timing, totals by model, cost by
session, and grand totals.

```
gmlw export <job> [--json]
```

- `job` (positional, required) — the job identifier.
- `--json` — output as JSON instead of text.

Example:

```
gmlw export billing-api --json
```

## statusline

Render the status line. This command is invoked by the client's status-line hook, not
by hand — it reads the client's status payload from stdin and uses `GMLW_CLIENT`,
`GMLW_JOB`, and `GMLW_SESSION` from the environment to pick the right parser.

```
gmlw statusline
```

Takes no positionals or flags. See [CLIENTS.md](CLIENTS.md) for how each client's
status line is installed and parsed.

## workflow

Author and list workflows. Invoked with no action, prints its own help.

```
gmlw workflow new <name> [--client CLIENT]
gmlw workflow list [--json]
```

### workflow new

Author a new workflow by running the shipped `create-workflow` meta-workflow as a
metered authoring session (no job — it is hidden from `gmlw jobs`).

- `name` (positional, required) — the new workflow's name.
- `--client CLIENT` — which client to wrap; defaults to the configured default, or
  `claude`.

Example:

```
gmlw workflow new tidy-review
```

### workflow list

List the runnable workflows. The hidden `_common` and `create-workflow` folders are
never listed.

- `--json` — output as JSON instead of text.

Example:

```
gmlw workflow list
```

See [WORKFLOWS.md](WORKFLOWS.md) for the authoring flow and workflow layout.

## persona

List the selectable personas. Invoked with no action, prints its own help.

```
gmlw persona list [--json]
```

- `--json` — output as JSON instead of text.

Personas are selected in config, not on the command line
(`[companion] persona = "<name>"`); see [CONFIGURATION.md](CONFIGURATION.md).

Example:

```
gmlw persona list
```

## plugins

List the installed plugins. Invoked with no action, prints its own help.

```
gmlw plugins list [--json]
```

- `--json` — output as JSON instead of text.

Plugins live at `~/.gmlw/plugins/<id>/` (each with a `plugin.toml`) and are wired in via
`[callers] <client> = "<id>"`. See [CONFIGURATION.md](CONFIGURATION.md).

Example:

```
gmlw plugins list
```

## creds

Manage per-workflow credentials. Invoked with no action, prints its own help.

```
gmlw creds set <workflow> <ENV_VAR_NAME>
```

### creds set

Store a credential for a workflow. The value is read securely: a hidden prompt at a TTY,
otherwise one line from stdin. It is written `0600` into `~/.gmlw/credentials.toml` and
injected into the child process environment as `ENV_VAR_NAME` at launch.

- `workflow` (positional, required) — the workflow the credential belongs to.
- `name` (positional, required) — the environment-variable name to export at launch.

Example:

```
gmlw creds set deploy-bot DEPLOY_TOKEN
```

---

## config

View and change the settable `~/.gmlw/config.toml` settings. Every key is backed by a
typed registry (its type, default, allowed values, and description); `set` validates
against it and merges the change into your file, preserving comments and formatting.
Invoked with no action, prints its own help.

```
gmlw config list [--json]
gmlw config get <key> [--json]
gmlw config set <key> <value>
```

### config list

List every setting with its current value and description.

### config get

Show one setting — its value, description, default, and any allowed values.

- `key` (positional, required) — the dotted setting key (e.g. `profile.default_role`).

### config set

Change one setting. The value is validated against the registry (type and allowed
values) before anything is written; the change is echoed (old → new), never silent. Use
`none` to clear an optional key back to its default.

- `key` (positional, required) — the dotted setting key.
- `value` (positional, required) — the new value.

Example:

```
gmlw config set profile.default_role reviewer
gmlw config set logging.level debug
gmlw config get client.default
```

The home for changing `default_role` / `default_environment` after `init`.

---

## help

Explain a core concept. `gmlw help` lists the topics; `gmlw help <topic>` prints one.

```
gmlw help
gmlw help <topic>
```

- `topic` (positional, optional) — one of `job-vs-workflow`, `start-vs-run`, `personas`,
  `cost`. Omit to list the topics. An unknown topic exits non-zero with guidance.

Bare `gmlw` (no arguments) is first-run-aware: on a fresh install it runs `init`;
thereafter it prints a grouped capability index (**launch / inspect / author**) with a
next-action footer. The flat argparse view is still available via `gmlw --help`.

---

## See also

- [USER_GUIDE.md](USER_GUIDE.md) — task-oriented walkthrough.
- [CONFIGURATION.md](CONFIGURATION.md) — `~/.gmlw/config.toml`, logging, personas, plugins.
- [WORKFLOWS.md](WORKFLOWS.md) — authoring and running workflows.
- [CLIENTS.md](CLIENTS.md) — supported clients and their capabilities.
- [../README.md](../README.md) · [../SECURITY.md](../SECURITY.md) · [../ROADMAP.md](../ROADMAP.md)
