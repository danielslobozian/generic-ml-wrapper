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

### 0.3.0 — lifecycle action hooks
gmlw already hooks **content**: the interceptor chain transforms context sections at
compile time and wire traffic at relay time (e.g. anonymisation on `request`). It now
also hooks **actions** — "after this phase, run something" — at two lifecycle seams
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
best-effort and never break a launch. Both launch paths (`start`, `workflow new`) route
through one shared launch sequence, so the seams bracket every run. Shipped with a
built-in `SessionLogger` reference hook.

**Still open — the flagship example hook:** a **cross-client skills/rules deployer** that
consumes a git repo of skills and installs them, per client, as faithfully as each
client's format allows. It is its own initiative (per-client format knowledge), built on
the seam above; the infrastructure is done and waiting for it.

#### Rule lifecycle
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

### 0.4.0 — first run: the forced setup that shapes every session
One job, done properly: a **mandatory `init`** every user passes through once — new or
existing — because it establishes the model the rest of the app runs on and migrates the
on-disk layout to match. It is a *forced update*: the old single-context folder layout is
wrapped into the new one non-destructively, and role + environment are chosen before the
first session. The discoverability work that used to sit here has moved to 0.5.0; this
release is the init and the two concepts under it.

**The movie-set model.** A launch composes four axes — three describe *you and your
context* (they become the briefing the wrapper hands the companion), one describes *the
companion itself*:

- **Me — the actor.** Who you are, invariant across everything: name, language, the
  journal. Spans every launch.
- **Role — the character.** The functional hat you're wearing (software engineer, product
  owner, QA, a private individual buying groceries). A *lens over `me`*, not a copy — it
  parameterises the `me`-extraction (which facets are in scope) and scopes rules/learned.
  You stay one person; you play different parts.
- **Environment — the movie set.** Where the work happens (work-at-a-company, a personal
  project, open source). It swaps the *place-specific context* — today's forced `company`
  becomes one environment's bucket. Changing environment changes the set and the
  guidelines, not who you are.
- **Persona — the director.** The one entity you actually talk to: the companion. Persona
  is *its* manner (manner over method — see 0.6.0).

gmlw itself is the **stage organiser / assistant director**: it builds the set, arranges
costume and makeup, briefs the director, then cedes the screen ([[wrapper-not-standalone]]).

- **Forced init (`gmlw init`, and the gate)** — init is both a command and a first-class
  gate: a stored marker records that it ran, and bare `gmlw` routes an un-initialised or
  old-layout install into it before anything else runs. It captures, in order, **language
  → name → role → environment → persona**, then does the technical client step. Each
  answer carries a sensible default so the forced pass stays short.
- **Two new concepts — role & environment** — the two axes above, made real: `default_role`
  and `default_environment` in `config.toml` (read directly — no registry yet), a
  `profile/roles/<role>/` folder for role-scoped rules/learned, and an
  `environments/<env>/` folder for place-specific context. Both are changeable later (via
  the `config` commands landing in 0.5.0). This **resolves the parked _profiles_ fork** —
  `me` spans, role is a lens over it, environment is the external place — by splitting one
  container into two orthogonal axes.
- **Forced migration** — the existing global layout (`profile/company`, single-context
  `rules`) is wrapped non-destructively into the new shape — `profile/company` →
  `environments/work/`, a `default` role seeded — surfacing exactly what moved
  ([[no-silent-removals]]). No install is left on the old layout.
- **Localised setup (EN / FR)** — onboarding strings move into a keyed language file
  (`i18n/en.*`, `i18n/fr.*`) read through a small `t(key, lang)` lookup with English
  fallback; the default is seeded from `$LANG`. Mechanism built to extend; content scoped
  to onboarding for now.
- **`language` — our voice only** — a `language` setting fixes the language gmlw speaks to
  *you* (onboarding now, receipts/help later). It does **not** force the companion's
  language: only Claude Code exposes a real language setting; Cursor, Codex and Vibe have
  none, so pushing it would be a leaky per-client hack for one client out of four. gmlw
  speaks your language; the companion stays as its own config leaves it.
- **A working client — the one hard requirement** — after the human setup, the technical
  step. *Fast path*: detect an installed, authenticated client and reach a session in
  seconds. *Guided path* when none is found: a subscription→client map (*"do you pay for
  Claude / ChatGPT / Cursor / Mistral?"*), the **official install command for the detected
  OS** (Windows / Linux / macOS), and **guide-and-verify auth** — print the exact login
  command, poll readiness until it goes green (guide, don't drive).
- **A default persona** — the experience-defining choice, offered with a one-line
  description per persona so it can be made without reading docs.

Deferred but homed: a detached model call to synthesise a `role.md` for an unfamiliar role
(e.g. product owner) is a natural future consumer of the 0.3.0 `pre-launch` seam — parked,
not built. **Persona *previews* moved to 0.8.0** — sample lines are only worth shipping once
the personas behind them are proven to actually differ, and doing them in French requires
localising persona content, which is the same job (see 0.8.0).

### 0.5.0 — discoverability & progressive disclosure
Reframed around the real metric for a new user: **time to a first live session**, and then
revealing depth *gradually*. Because the wrapper cedes the screen to the client, discovery
lives in the thin surfaces **around** a run — bare-command indexes, the return, and ambient
context pushed *into* the client — never a persistent UI over a live session.

- **App-wide localisation** (`0fe8c0a`) — the init-only JSON catalogue now spans the whole
  app: every user-facing message **and every diagnostic log line** renders through a
  process-global active localiser (`i18n.set_active`/`active`/`t`), English-fallback then
  raw-key safe. A catalogue-drift guard keeps EN/FR key sets identical. Localising the logs
  too was a deliberate choice, not the usual English-only-logs convention.
- **Config registry** (`9fe05b6`) — a `pydantic-settings` model is the typed source of
  truth for every settable scalar key (type, default, allowed values, description);
  `registry_rows()`/`coerce()`/`load()` drive help, `config`, and validation. `config.py`
  sources its defaults from it (no duplicated literals) while keeping its tolerant reads.
  *Scope:* scalar keys only — the structural matrices (`[[hooks]]`, `[[interceptors]]`,
  `[startup.*.context]`, `[compress.prompts]`) stay hand-rolled, a deferred follow-up.
- **`config` commands** (`0db3ca7`) — `config list / get / set`, rendering + validating
  against the registry; `set` merges through the shared tomlkit writer (comments preserved,
  never rewritten) and surfaces the old→new change. The home for changing `default_role` /
  `default_environment` after init.
- **Bare `gmlw` + `gmlw help`** (`61bb15f`) — bare `gmlw` is first-run-aware: fresh install
  → init; thereafter → a grouped capability index (*launch / inspect / author*) with a
  next-action footer. `gmlw help <topic>` explains the core concepts (job-vs-workflow,
  start-vs-run, personas, cost). `--help` keeps the argparse view.
- **Greeting → context** (`85a77da`) — the launch-time host greeting (structurally
  invisible once the client clears the screen) is retired from stderr and injected into a
  new session's context, so the client renders it in-band. `_farewell` (exit) stays.
- **Exit receipt + ambient card** (`f36fcd8`) — on the return, a persistent receipt: this
  session's and the job's cost, the resume/report commands, and one usage-driven,
  suppressible tip (shown once each; `[hints] show` to disable). `StartJob` returns a
  `StartJobResult` so the receipt can name the session. The off-by-default ambient
  capability card (`[ambient] capability_card`) injects a "how do I …" gmlw card into the
  context. **Authoring-cost visibility deferred** — the authoring bucket is deliberately
  kept out of `gmlw jobs`; surfacing its spend cleanly is its own design.
- **`workflow edit`** (`0445c6d`) — amend an existing workflow in an authoring session
  (opens its folder, never creates/overwrites; unknown name → clean error).
- **Already shipped earlier, verified here:** **`--version`** (surfaces the running version)
  and **robustness** (clean Ctrl+C / SIGTERM interrupt-exit) were already present; their few
  strings were folded into the app-wide localisation pass.

## Planned

### 0.6.0 — the workflow, first-class
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

#### Statusline — render the data Claude Code already hands us
A separate, self-contained thread riding in this release: the status payload gmlw
receives already carries more than it displays, and two of those fields are parsed out
and dropped. No new plumbing — the data arrives at the status parser today; the fix is to
keep it and render it. Claude-first (the cursor parser shares the context shape and
benefits where the fields overlap); codex and vibe pipe no status payload, so this
degrades honestly rather than fabricating a denominator.

- **Show the denominator** — today gmlw renders a bare `78%` against an *unstated*
  window size. The payload also carries `context_window_size` (200k default, 1M for
  extended-context models), so render `155.6k/200k (78%)` instead. This is what makes the
  percentage falsifiable: a Max user who sees `/200k` knows the window is being
  under-reported (the metering relay looks like a gateway, so Claude Code can't verify 1M
  support and budgets 200k) and can act on it themselves. Extend the client status with
  `context_window_size` and `context_tokens`.
- **Quota: time-to-reset, not just percentage** — `5h 90%` is unactionable without
  knowing whether reset is in 10 minutes or 4 hours. The payload carries `resets_at`
  (epoch seconds) per window; render it as a relative duration — `5h 90% (↻12m) · wk 40%
  (↻3d)`. Each window may be independently absent (subscriber-only, appears after the
  first response), so tolerate a missing reset per field exactly as the percentage
  already is. The single most decision-relevant pair a metering wrapper can show.
- **Baseline & drift (candidate)** — a session that opens at 26% full looks identical to
  one at 5% until it's too late. A pre-launch / first-turn line surfacing the baseline
  cost (tools · mcp · skills), and a note when the baseline drifts upward across a client
  auto-update. Softer than the two above; carried as a candidate, not a commitment.

### 0.7.0 — TUI refactoring: the terminal UX as one system
The discoverability surfaces landed piecemeal across 0.4.0–0.6.0 — the first-run chooser, the
bare-`gmlw` index, `help` topics, `config list`, the exit receipt, the ambient card, the
pre-launch workflow chooser. Each was built when its feature needed it. This release stops
adding surfaces and makes the ones that exist read as **one system**: a consistency and
quality pass over the terminal UX, from the design deliverable in `generic-ml-wrapper-030-ui-concepts.md`.

**Not a TUI app.** The curses/full-screen "Hub" (that doc's Concept 3) stays **dropped** — it
carries the only real dependency bill, and a persistent full-screen surface pulls against
[[wrapper-not-standalone]]. "TUI refactoring" here means refactoring the *text* UX gmlw already
owns, not adopting a widget toolkit. gmlw's UI lives only on the five legal surfaces and never
as a persistent UI over a live session.

- **The five surfaces, made consistent** — utility commands (S1), pre-launch (S2), the handoff
  (S3), ambient in-client greeting/statusline (S4), and **the return** (S5). Audit each for the
  house rules the codebase already implies: chrome to stderr so stdout stays clean for `--json`,
  non-TTY degrades to silent/scriptable, and anything shown at the handoff (S3, instantly wiped)
  is duplicated at S4/S5 so nothing is lost.
- **Next-action footers everywhere** — the core mechanic of the enriched CLI: every
  run-and-return command ends with 1–2 contextual next commands, so discovery rides on commands
  the user already runs. Make it uniform across *all* listings/inspections, not just the ones
  that happen to have it.
- **The chooser teaches the fast path** — the pre-launch chooser always echoes the equivalent
  one-liner before handoff, and `?` at any prompt prints the relevant `help` topic inline then
  re-prompts, so interactive use graduates the user out of the chooser. Full argv still means
  zero interaction, always.
- **Receipt / card parity** — the exit receipt (S5) and the ambient capability card (S4) must
  describe the same command surface in the same vocabulary, so "what can gmlw do" gets the same
  answer whether asked mid-session or read on the return. One suppressible, usage-driven tip per
  return, rotated, never off-TTY.
- **A visual-consistency pass** — shared alignment, colour/emphasis conventions, and the
  status-of vs manual split (statusline = ambient *state*; card = ambient *manual*) applied
  uniformly, so the surfaces look like one product rather than several sittings.

### 0.8.0 — personas, proven (and multilingual)
Today "personas shape tone" is an **untested claim**. A persona ships a tone block, but
nothing demonstrates that `mentor` and `terse` actually answer differently — and the tone
block is injected *on top of* each client's own system prompt, which may simply swamp it.
This release makes the claim falsifiable first, then builds on it. Its own initiative: it
is an evaluation loop, not a feature.

- **A persona evaluation harness** — the core of the release. Run every persona against a
  fixed question set and compare. Two design calls, both deliberate:
  - **Questions curated against the declared dimensions, not scraped.** Generic benchmark
    sets measure *correctness* and would show almost no tone variance. Each persona already
    declares `Warmth · Verbosity · Formality · Proactivity`, so the set probes exactly those,
    plus the high-divergence moments — being corrected, delivering bad news, being handed a
    half-formed request.
  - **A distinctness metric, not eyeballing.** A judge scores each answer on the declared
    dimensions and yields a **pairwise distance matrix**, so collapsed pairs are named rather
    than sensed (`plain`/`terse` and `companion`/`mentor` are the likely offenders). Runs go
    through **generic-ml-cache**, so re-running one persona after a tweak replays the other
    four for free and keeps iterations deterministic and diffable.
- **Tune until distinct** — the back-and-forth the harness exists to serve: adapt each tone
  block, re-run, watch the matrix separate. The honest possible outcome is that personas must
  become **bolder** to survive a client's own voice — or that they differentiate on some
  clients and not others. That finding is a deliverable, not a failure.
- **Per-workflow persona, composed as voice over method** — a workflow can carry its own
  persona instead of the single global tone. Persona is **manner**; the facilitative +
  constructive authoring behavior (0.6.0) is **method**. They compose by layer: the method
  lives in the mode floor (guaranteed, persona-independent), and the persona colors delivery
  on top — it can voice the invariants but not break them. Personas carry an
  **authoring-friendliness** expectation, so a voice built around brutal efficiency can't
  sabotage the facilitation. *Landed here, after the harness proves the personas actually
  differ* — layering per-workflow persona on top of personas that collapse would build on
  sand, so composition follows the proof rather than preceding it.
- **Persona content becomes multilingual** — required for previews in French, and a real gap
  today: only the *prompt header* is localised, so a French user gets an English description
  and an **English greeting at every launch**. This is not a strings port: French carries a
  `tu`/`vous` register English cannot express, and a butler is *defined* by register — so the
  directives themselves need per-language authoring, not translation.
  - Layout: a **folder per persona** — a language-neutral `body.md` (dimensions, do/don't)
    plus `en.md` / `fr.md` carrying description, greeting, register notes, and samples.
  - **A flat `<name>.md` must keep working.** Users author personas by dropping a file in
    `~/.gmlw/personas/`; a folder gets the full treatment, a flat file behaves as it does
    today (English, no samples, falls back to its description). Breaking user-authored
    personas to gain previews would be a bad trade.
- **Previews, as a byproduct** — once the answers are generated, reviewed, and committed as
  data, the first-run chooser can show a real sample line per persona. It stays **static** at
  runtime: generated at authoring time, read from disk, **zero tokens and zero latency**, so
  choosing still costs nothing. Length forces a split — one short line inline in the chooser,
  the full side-by-side behind `gmlw persona preview`. Samples are labelled as indicative:
  they come from one model at authoring time, and the user's client may differ.

**Sequencing, resolved:** *per-workflow persona* used to sit in 0.6.0, ahead of the release
that proves personas are distinct at all — building composition on an unproven foundation. It
now lives here in 0.8.0, after the harness and the tuning, so the composition follows the
proof. If the matrix shows personas collapse even after tuning, per-workflow persona is
reconsidered in place rather than shipped on sand.

## Parked

- **External source connectors** — let a workflow pull from external systems (APIs,
  cloud storage, platforms) rather than manual input. Large; its own initiative.
- Relay extraction to a standalone project (shelved — no second consumer yet).
- Workspace layout feature.
