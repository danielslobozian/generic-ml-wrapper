# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-14

First public release — a metering wrapper around ML coding CLIs.

### Added
- **Jobs & sessions.** Enter at a **job** you tag; the wrapper mints a named,
  resumable **session** on the client and persists it. `gmlw start`, `jobs`,
  `sessions`, `export`.
- **Four clients** driven the same way: **claude**, **cursor**, **codex**, **vibe**.
  Which one is config-driven (`[client]`) or `--client`.
- **Metering relay.** A local, capability-URL-authenticated relay records **per-turn
  tokens and cost** for the metered clients (claude/codex/vibe) into a SQLite ledger;
  `gmlw export` reports per-turn rows, per-model totals, and per-session cost.
- **Status line** for the clients that host one (claude, cursor): git · folder ·
  model · context% · a client-specific allowance block, plus a per-session and
  per-job usage footer.
- **Workflows.** Author a small operating context once (`gmlw workflow new`, a warm
  create-workflow interview) and launch a job with it; context is compiled from a
  shared base + your profile + rules + the workflow steps, through an interceptor
  chain (with opt-in context compression via `generic-ml-cache`).
- **Durable provenance.** The exact compiled context is written per session
  (`contexts/<job>/<session>.context.md`); an **opt-in transcript** keeps each metered
  call's request/response/usage.
- **Credentials.** Per-workflow secrets stored `0600` and injected into the client's
  environment at launch (`gmlw creds set`).
- **Storage.** A single SQLite ledger (`~/.gmlw/ledger.db`, WAL) for jobs, sessions,
  per-turn usage, and session costs.
- **Safety.** Validated `JobId` + filesystem containment under an owner-only `~/.gmlw`;
  never overwriting an unparseable client-settings or credentials file.

### Engineering
- Hexagonal (ports & adapters), enforced by `import-linter`; strict `ruff` + `pyright`
  over `src` and `tests`; `nox` gates mirrored by CI across Python 3.11–3.14; a
  server-side no-AI-attribution check and branch protection.

[Unreleased]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/danielslobozian/generic-ml-wrapper/releases/tag/v0.1.0
