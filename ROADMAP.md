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
not built. **Persona *previews* moved to 0.7.0** — sample lines are only worth shipping once
the personas behind them are proven to actually differ, and doing them in French requires
localising persona content, which is the same job (see 0.7.0).

## Planned

### 0.5.0 — discoverability & progressive disclosure
Reframed around the real metric for a new user: **time to a first live session**, and then
revealing depth *gradually* rather than dumping it up front. Because the wrapper cedes the
screen to the client, discovery lives in the thin surfaces **around** a run — bare-command
indexes, the return, and ambient context pushed *into* the client — never a persistent UI
over a live session.

- **Bare `gmlw` is first-run-aware** — first time → the 0.4.0 init; thereafter → a grouped
  capability index (*launch / inspect / author*), with `gmlw help <topic>` for the core
  concepts (job vs workflow, start vs run, personas, cost). `--help` keeps the argparse
  view; every listing ends with a next-action footer.
- **Config registry** — one typed source of truth (a `pydantic-settings` model) for every
  setting: key, type, default, allowed values, description. It replaces the hand-rolled
  accessors, and every surface (help, `config`, per-workflow settings, the 0.4.0
  role/environment keys) renders from it.
- **`config` commands** — `config list / get / set`, rendering the registry with inline
  allowed-value validation. The home for changing `default_role` / `default_environment`
  after init.
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
- **App-wide localisation** — the JSON string catalogue introduced for the 0.4.0 init
  graduates from onboarding-scale copy to the *whole app*: **every** message the app
  emits to the user **and every line it writes to a log** routes through the localiser, so
  the running language governs all output rather than just the first run. Today only a
  handful of modules speak through `i18n.t`; the rest are raw `print` / `logging` calls
  hard-coded in English. The work is to funnel those through the catalogue, grow
  `resources/i18n/<lang>.json` to cover them, and keep the English-merged fallback so an
  untranslated key still degrades to English, never a raw key. Localising the logs too is
  a deliberate choice — not the usual English-only-logs convention.
- **Robustness** — clean interrupt/exit: catch Ctrl+C / an interrupt so leaving a client
  session ends cleanly instead of surfacing the child's raw error.

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
- **Per-workflow persona, composed as voice over method** — a workflow can carry its own
  persona instead of the single global tone. Persona is **manner**; the authoring
  behavior above is **method**. They compose by layer: the method lives in the mode
  floor (guaranteed, persona-independent), and the persona colors delivery on top — it
  can voice the invariants but not break them. Personas carry an **authoring-friendliness**
  expectation, so a voice built around brutal efficiency can't sabotage the facilitation.

### 0.7.0 — personas, proven (and multilingual)
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

**Sequencing risk, stated plainly:** 0.6.0 layers *per-workflow persona* on top of personas
whose distinctness this release is what proves. If the matrix shows they collapse, 0.6.0's
persona composition needs revisiting — so pull this earlier if that work starts leaning hard
on the foundation.

## Parked

- **External source connectors** — let a workflow pull from external systems (APIs,
  cloud storage, platforms) rather than manual input. Large; its own initiative.
- Relay extraction to a standalone project (shelved — no second consumer yet).
- Workspace layout feature.
