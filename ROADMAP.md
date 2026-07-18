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

#### Rule lifecycle — done (Unreleased)
0.2.0 shipped rule *capture*, but only inside a workflow (the directive lived in the
workflow base) and without dedup or a path to code. The rule loop is now rounded out —
the directive moved out of the workflow base to the head of the always-on `rules`
context source (verbatim, gmlw's voice), and the source is active by default in a plain
start:

- **Rule proposal in normal usage** — the "offer to record a rule" directive is
  always-on, so a demanded correction becomes a draft rule wherever it happens, not only
  inside a workflow.
- **Existing-rule check (dedup / update-not-duplicate)** — before proposing, the client
  reads the existing rules and updates or supersedes a matching one instead of stacking a
  near-duplicate, mirroring the learned notebook's supersede-on-contradiction.
- **Rule → code feasibility** — a captured rule is judged for *mechanical
  enforceability* and, if so, offered as a script/check rather than a reminder — the
  step-codeability logic (create-workflow) generalised from workflow steps to rules, and
  a natural future `pre-launch` hook consumer.

### 0.4.0 — discoverability & first-run: getting captivated fast
Reframed around the real metric for a new user: **time to a first live session.**
Captivation lives in the model session, not the wrapper — so the job is to remove
everything between a stranger and that first response, then reveal depth *gradually*
(progressive disclosure). Because the wrapper cedes the screen to the client, discovery
lives in the thin surfaces **around** a run — pre-launch, run-and-return commands, the
return, and ambient context pushed *into* the client — never a persistent UI over a
live session.

- **First-run onboarding** — on first launch, a greeting instead of the help menu:
  *"looks like your first time — set up (about a minute), or skip? (`gmlw init`
  anytime)."* Setup establishes the two things that shape every later run:
  - **A working client** — the one hard requirement (no client, no session). *Fast path*
    when a client is already installed and authenticated: detect it and reach a session
    in seconds. *Guided path* when none is: a subscription→client mapping (*"do you pay
    for Claude / ChatGPT / Cursor / Mistral?"* → the matching supported client CLI), a
    link/script to install, and **guide-and-verify auth** — print the exact login
    command, then poll readiness until it goes green (guide, don't drive the login).
  - **A default persona** — the experience-defining choice (otherwise every launch needs
    a flag). Picked from **static previews** (sample lines per persona), not a live
    model quiz, so choosing costs nothing.
- **Bare `gmlw` is first-run-aware** — first time → the greeting/onboarding; thereafter →
  a grouped capability index (*launch / inspect / author*), with `gmlw help <topic>` for
  the core concepts (job vs workflow, start vs run, personas, cost). `--help` keeps the
  argparse view; every listing ends with a next-action footer.
- **Config registry** — one typed source of truth (a `pydantic-settings` model) for
  every setting: key, type, default, allowed values, description. It replaces the
  hand-rolled accessors, and every surface (help, `config`, per-workflow settings)
  renders from it — so the config file no longer has to be pre-populated to be found.
- **`config` commands** — `config list / get / set`, rendering the registry with inline
  allowed-value validation.
- **`--version`** — surface the running version.
- **Progressive disclosure** — depth is revealed over time, not dumped up front:
  - **Exit receipt** — on the return (client exit), a persistent summary: this session's
    and the job's cost, the resume/report commands, and one usage-driven, suppressible
    tip (the channel that surfaces features as they become relevant). Also the home for
    **authoring-cost visibility** — workflow authoring is already a metered session;
    surface it in listings/export instead of hiding it, keeping the work/authoring split.
  - **Ambient capability card** — an optional, off-by-default context injection so the
    client itself answers "how do I …" gmlw questions mid-session. Kept minimal and
    counted against the context budget.
- **Greeting → context** — retire the launch-time host greeting (structurally invisible:
  the client clears the screen) and inject it as a context instruction the client
  renders in-band, with live metadata (time, name, recent activity).
- **`workflow edit`** — update an existing workflow, not only create.
- **Robustness** — clean interrupt/exit: catch Ctrl+C / an interrupt so leaving a client
  session ends cleanly instead of surfacing the child's raw error.

### 0.5.0 — the workflow, first-class
Two ways people relate to a workflow: *applied to a job* (a ticket it treats), or *the
recurring job itself* (a repeatable extraction). Make both first-class, and make
authoring one a guided conversation — because most people don't arrive with a clear
model of their own process.

- **`run <workflow>`** — launch a workflow directly; the job defaults to the workflow
  name and sessions accumulate under it. `start <job> [--workflow]` stays for the
  applied case. A trigger-gated pre-launch chooser fills only *missing* arguments and
  always echoes the equivalent one-liner, so interactive use teaches the fast path
  (full argv never gains a prompt).
- **Name at the end, not the start** — `workflow new` no longer demands a name up front;
  forcing one presumes the user already knows the shape. The authoring conversation
  shapes the workflow and *proposes* the name at convergence. (Distinct from
  `run <workflow>`, where an existing, recurring workflow's name has already earned it.)
- **Facilitative + constructive authoring** — the create-workflow conversation as a
  blended consultant. Two axes: *facilitate* (a **parking lot** for tangents so nothing
  is lost, reflective listening, a **diverge → converge** phase model, and **process
  leveling** to answer "step or its own workflow?") and *contribute* (start in inquiry
  and **move to expert when warranted**, propose the upstream/downstream stages the
  author omitted, surface **implications** they haven't hit) — bounded by guardrails
  against railroading a novice and a **consent gate** on anything personal. Authoring
  keeps distilled state (a draft plus the parking lot) as files in the workflow folder,
  so it survives context compaction.
- **Per-workflow persona, composed as voice over method** — a workflow can carry its own
  persona instead of the single global tone. Persona is **manner**; the authoring
  behavior above is **method**. They compose by layer: the method lives in the mode
  floor (guaranteed, persona-independent), and the persona colors delivery on top — it
  can voice the invariants but not break them. Personas carry an **authoring-friendliness**
  expectation, so a voice built around brutal efficiency can't sabotage the facilitation.

## Parked

- **External source connectors** — let a workflow pull from external systems (APIs,
  cloud storage, platforms) rather than manual input. Large; its own initiative.
- Relay extraction to a standalone project (shelved — no second consumer yet).
- Workspace layout feature.
