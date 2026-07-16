# CLI reference

Complete command reference for the `gmlw` console script (generic-ml-wrapper v0.2.0).
This page documents exactly what `build_parser()` exposes — every command, positional,
and flag. For deeper behaviour, follow the cross-links to [CONFIGURATION.md](CONFIGURATION.md),
[WORKFLOWS.md](WORKFLOWS.md), and [CLIENTS.md](CLIENTS.md).

## Synopsis

```
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

## See also

- [USER_GUIDE.md](USER_GUIDE.md) — task-oriented walkthrough.
- [CONFIGURATION.md](CONFIGURATION.md) — `~/.gmlw/config.toml`, logging, personas, plugins.
- [WORKFLOWS.md](WORKFLOWS.md) — authoring and running workflows.
- [CLIENTS.md](CLIENTS.md) — supported clients and their capabilities.
- [../README.md](../README.md) · [../SECURITY.md](../SECURITY.md) · [../ROADMAP.md](../ROADMAP.md)
