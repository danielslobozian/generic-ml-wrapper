<!-- SPDX-FileCopyrightText: 2026 Daniel Slobozian -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Roadmap

Where `generic-ml-wrapper` has been and where it's going. Direction, not a
commitment — see [CHANGELOG.md](CHANGELOG.md) for what has actually shipped.

The through-line: turn a metering wrapper into something a person *wants* to open —
a companion that carries **who you are and how you work across every client**, and
stays a wrapper (it extends each client; it never reimplements one).

## Shipped

### 0.1.0
The metering foundation — jobs & sessions, four clients (claude / cursor / codex /
vibe), a per-turn metering relay into a SQLite ledger, a client-aware status line,
and the workflow system. On PyPI.

### 0.2.0 — the companion
Everything a session inherits, and the ergonomics around it.

- **First-run init** — detect installed clients, seed a filled config with a default.
- **Config-driven, mode-aware context packaging** — a `[startup.<mode>]` matrix picks
  which sources compose (persona · profile · learned · company · rules · workflow
  base/steps) for each mode (default / workflow / authoring), with **typed per-source
  compression** (`[compress.prompts]`).
- **Personas** — selectable tone with a universal floor; `gmlw persona list`; a free,
  local **host greeting** at launch; a first-run persona choice.
- **Learned** — a portable, user-owned notebook the client mirrors into, read into
  every client so what one learns they all inherit; **negatives are first-class**.
- **Rule format** — a domain-neutral `Rule / When / Signals / Strength / Origin`
  (+ optional `Precedence`), with in-session capture during a workflow.
- **Formal plugins folder** — reference a caller by id (`~/.gmlw/plugins/<id>/`),
  `gmlw plugins list`.
- **Cursor allowance block** — the status line renders cursor's plan pools from an
  optional local cache when the client doesn't pipe them.
- **Ergonomics** — client & working-directory preflight (clear guidance instead of a
  cryptic crash), implicit `gmlw <job>` (shorthand for `start`), a friendly no-job
  message, and auto-help for an incomplete sub-command.
- **Create-workflow** — the interviewer assesses each step's *codeability* and offers
  to script the mechanical ones, keeping the AI for the judgment steps.

## Planned

### 0.3.0 — lifecycle action hooks
gmlw already hooks **content**: the interceptor chain transforms context sections at
compile time and wire traffic at relay time (e.g. anonymisation on `request`). 0.3.0
adds **action** hooks — "after this phase, run something" — at two lifecycle seams
that bracket the client run:

- **`pre-launch`** — after the context is compiled and the caller resolved, before the
  client starts. Knows the client, the working directory, and the session. For
  per-client setup: deploying skills/rules into a client's *native* mechanism, writing
  MCP config, warming a cache.
- **`post-session`** — after the client exits. Knows the exit code and the session.
  For cleanup, notification, archival, or roll-up.

Config mirrors the existing extension points — a `[[hooks]]` entry with a `phase`, a
`spec` (a plugin id or `path.py:Class`), and an optional `client` scope — under the
same trusted-code boundary as `[[interceptors]]`, `[callers]`, and plugins. Hooks are
best-effort and never break a launch. The first example hook: a **cross-client
skills/rules deployer** that consumes a git repo of skills and installs them, per
client, as faithfully as each client's format allows.

## Parked

- Relay extraction to a standalone project (shelved — no second consumer yet).
- Workspace layout feature.
