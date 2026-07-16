<div align="center">

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/gmlw-lockup-dark.svg">
  <img src="docs/images/gmlw-lockup.svg" alt="gmlw" width="200">
</picture>

#### A metering wrapper around your ML coding CLI

Run **claude**, **cursor**, **codex**, or **vibe** exactly as you know them — but on a **job** you tag, in a **named, resumable session**, with **every turn's tokens and cost recorded**. An application that uses an ML client, not an ML client pretending to be an application.

<br>

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-185FA5?style=for-the-badge&labelColor=403E3A)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/danielslobozian/generic-ml-wrapper/ci.yml?branch=main&style=for-the-badge&labelColor=403E3A&label=ci)](https://github.com/danielslobozian/generic-ml-wrapper/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/sonar/coverage/danielslobozian_generic-ml-wrapper?server=https%3A%2F%2Fsonarcloud.io&style=for-the-badge&labelColor=403E3A)](https://sonarcloud.io/summary/overall?id=danielslobozian_generic-ml-wrapper)
[![Python](https://img.shields.io/badge/python-3.11%E2%80%933.14-185FA5?style=for-the-badge&labelColor=403E3A)](pyproject.toml)

[![client: claude](https://img.shields.io/badge/client-claude-534AB7?style=for-the-badge&labelColor=3C3489)](src/generic_ml_wrapper/adapter/outbound/caller/claude_cli_caller.py)
[![client: cursor](https://img.shields.io/badge/client-cursor-534AB7?style=for-the-badge&labelColor=3C3489)](src/generic_ml_wrapper/adapter/outbound/caller/cursor_cli_caller.py)
[![client: codex](https://img.shields.io/badge/client-codex-534AB7?style=for-the-badge&labelColor=3C3489)](src/generic_ml_wrapper/adapter/outbound/caller/codex_cli_caller.py)
[![client: vibe](https://img.shields.io/badge/client-vibe-534AB7?style=for-the-badge&labelColor=3C3489)](src/generic_ml_wrapper/adapter/outbound/caller/vibe_cli_caller.py)

<br>

[Why a wrapper](#why-a-wrapper) &nbsp;•&nbsp; [Clients](#clients-at-a-glance) &nbsp;•&nbsp; [The job](#the-job) &nbsp;•&nbsp; [Install](#install) &nbsp;•&nbsp; [Workflows](#workflows) &nbsp;•&nbsp; [What it records](#what-it-records) &nbsp;•&nbsp; [Guides](#guides) &nbsp;•&nbsp; [Design](docs/DESIGN.md)

</div>

<br>

---

## Why a wrapper

The raw coding CLIs are black boxes. A session has no name you chose, so you can't find it again. A run's cost is invisible — you never learn what a task actually spent. The exact context a session launched with is gone the moment it starts. And every client does all of this differently, so nothing you learn about one transfers to the next.

`gmlw` is a thin, deterministic shell around the client that keeps the client's behaviour intact and adds the parts an *application* needs:

- **Identity** — you enter at a **job** you tag; the wrapper mints a named, resumable session on the client.
- **Metering** — a local relay sits between the client and its upstream API and records **tokens and cost per turn**, for any metered client, without changing a single thing about how the client runs.
- **Provenance** — the compiled context a session launched with is written to disk; opt in to a full **transcript** and every call's request, response, and usage is kept too.
- **One surface** — claude, cursor, codex, and vibe are all driven the same way and land in the same ledger.

The judgment stays in the client. The deterministic parts — session identity, launch, context compilation, persistence, metering — are Python you can read.

<div align="center">
<img src="docs/images/gmlw-usage.gif" alt="gmlw export — per-turn tokens and cost for a job" width="760">
</div>

## Clients at a glance

Four clients, one surface — but they are **not** identical. What each supports today:

| Client | Metering | Resume | Status line | Context delivery |
|---|:---:|:---:|:---:|---|
| **claude** (`claude`) | ✅ | ✅ | ✅ | native `--append-system-prompt-file` |
| **cursor** (`cursor-agent`) | ❌ | ✅ | ✅ | context-file instruction |
| **codex** (`codex`) | ✅ | ❌ | ❌ | initial instruction |
| **vibe** (`vibe`) | ✅ | ❌ | ❌ | initial instruction |

Cursor isn't metered by the open-source wrapper (its usage isn't on an interceptable API); Codex and Vibe don't resume. See [`docs/CLIENTS.md`](docs/CLIENTS.md) for the per-client detail and setup.

## The job

A **job** is the one concept everything hangs off. It's the piece of work you're tagging — a ticket, a refactor, an investigation — and it is the primary key of the whole ledger.

```
job  ──►  sessions  ──►  turns ──► tokens + cost
                    └───► context.md (what it launched with)
                    └───► transcript (opt-in: in / out / usage per call)
```

You start work at a job and read it back by job:

```sh
gmlw start REFACTOR-42                 # mint + launch a session on the default client
gmlw start REFACTOR-42 --resume-latest # pick the latest session back up
gmlw jobs                              # every job with recorded activity
gmlw sessions REFACTOR-42              # that job's sessions, oldest first
gmlw export REFACTOR-42                # per-turn tokens + cost, totalled by model
```

Nothing about the client changes — you get its full TUI. The wrapper owns the identity, the launch, and the persistence around it.

## Install

Requires Python 3.11–3.14 and [`uv`](https://docs.astral.sh/uv/), plus **one supported coding CLI already installed and logged in** (`claude`, `cursor-agent`, `codex`, or `vibe`). The console script is `gmlw`.

```sh
uv tool install generic-ml-wrapper     # or: uv sync --extra dev  (from a clone)
gmlw start MY-FIRST-JOB                # first run self-seeds ~/.gmlw (owner-only)
```

On first run the wrapper creates `~/.gmlw/` (mode `0700`) with a commented `config.toml`, a SQLite ledger, and the workflow/profile/rule folders. Pick the client per run with `--client claude|cursor|codex|vibe`, or set a default in `config.toml`.

## Workflows

A **workflow** is a small operating context you author once and launch a job with. Rather than re-explaining the same standing instructions to the client every time, you compile them once — a base, your profile, global rules, and the workflow's own steps — into the context the session opens with.

```sh
gmlw workflow new doc-review           # author a workflow (an authoring session, kept apart from work)
gmlw workflow list                     # the runnable workflows
gmlw start DOCS-1 --workflow doc-review # launch a job with that context compiled in
```

Workflows can carry their own credentials (`gmlw creds set <workflow> <ENV_VAR>`), injected into the child process at launch and stored `0600`. Context compilation runs through an **interceptor chain**, so a step like context compression is an opt-in plug-in, not a fork of the engine.

## What it records

Everything lives under `~/.gmlw/`, owner-only, on your machine:

| Artifact | Where | What |
|---|---|---|
| **Ledger** | `ledger.db` (SQLite, WAL) | jobs, sessions, per-turn token usage, per-session cost |
| **Context** | `contexts/<job>/<session>.context.md` | the exact compiled context the session launched with |
| **Transcript** *(opt-in)* | `transcripts/<job>/<session>/call_NNN.{in.json,out.sse,usage.json}` | every call's request, response, and usage — a portable, self-contained folder |

For **Claude Code** and **Cursor**, the wrapper renders a rich status line straight into the client's own status bar — the git branch, folder, model, context %, and live cost, plus the job's running total. (The status-line seam is client-agnostic; Claude and Cursor are wired today, and other parsers can be added.)

<div align="center">
<img src="docs/images/gmlw-statusline.gif" alt="the gmlw status line rendered for claude and cursor" width="760">
</div>

## Your operating context, carried across clients

Beyond metering, `gmlw` builds a portable operating context that follows you from one client to the next — none of it locked inside a single tool:

- **Profile & company** — who you are and your project's conventions (`profile/me`, `profile/company`), composed into every session.
- **Learned notebook** — what your tools notice about how you work, in one file they all mirror into; negatives ("what to avoid") are first-class.
- **Personas** — a selectable tone with a free, local greeting at launch (`gmlw persona list`).
- **Rules** — corrections you've demanded, captured as reusable reflexes (`~/.gmlw/rules/*.rule.md`).
- **Mode-aware packaging** — a `[startup.<mode>]` matrix decides which sources compose for a plain session, a workflow, or authoring, with optional typed compression.
- **Plugins & overrides** — swap a client's caller by id (`gmlw plugins list`, `[callers]`).

Workflows (above) are *optional* and separate from this personal layer. Every listing/reporting command also speaks `--json` for automation.

## What gmlw does not do

- It is **not a sandbox** — it launches the real client with your credentials (see [`SECURITY.md`](SECURITY.md)).
- It does **not** meter Cursor, and does **not** resume Codex or Vibe (see the [matrix](#clients-at-a-glance)).
- It does **not** call models itself — the optional context compressor records through [`generic-ml-cache`](https://github.com/danielslobozian/generic-ml-cache).
- It ships **no** compression prompts — the compressor stays inert until you configure one.

## Guides

- [User guide](docs/USER_GUIDE.md) — task-oriented, first launch through daily work.
- [CLI reference](docs/CLI.md) — every command, flag, and `--json` option.
- [Configuration](docs/CONFIGURATION.md) — every `config.toml` section, with examples.
- [Clients](docs/CLIENTS.md) — per-client behaviour, setup, and limitations.
- [Workflows](docs/WORKFLOWS.md) — authoring, layout, scripts, rules, credentials.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — failures, diagnostics, reset/recovery.
- [Design](docs/DESIGN.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

## Develop

The gates are defined once in [`noxfile.py`](noxfile.py); CI is a thin caller of them, so what runs locally is byte-for-byte what runs in CI.

```sh
uv sync --extra dev          # or: nox -s dev   (builds the IDE .venv)
nox                          # lint · imports · typecheck · tests (3.11–3.14)
nox -s green                 # the whole gate in one env (lint · format · imports · pyright · coverage)
```

Strict `ruff` + `pyright` (over `src` **and** `tests`), import-linter hexagon contracts, and an 80% coverage floor all run in the gate. Every change goes on a branch (`feature/… tech/… fix/… docs/… chore/… test/…`), keeps `nox -s green` passing, and merges via PR — direct pushes to `main` are blocked by branch protection.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the architecture, [`SECURITY.md`](SECURITY.md) for the threat model, and [`CONTRIBUTING.md`](CONTRIBUTING.md) to get set up.

## Family

Part of the `generic-ml-*` family, alongside
[`generic-ml-cache`](https://github.com/danielslobozian/generic-ml-cache) (record/replay execution cache — the wrapper's context compressor records through it) and
[`generic-ml-workflow`](https://github.com/danielslobozian/generic-ml-workflow).

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). Contributions welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).
