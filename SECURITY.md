# Security Policy

`generic-ml-wrapper` is early, pre-1.0 software (`0.1.0.dev0`). It is published openly
and takes security seriously regardless of maturity. Thank you for helping keep it and
its users safe.

## Supported versions

Before `1.0.0` there are no long-term support branches or backports — only the latest
release (or `main`) receives fixes. Please confirm an issue still reproduces there.

## Reporting a vulnerability

**Please do not open a public issue, pull request, or discussion for a security
vulnerability.** Public disclosure before a fix is available puts users at risk.

Report it privately through GitHub:

1. Go to the **Security** tab of this repository.
2. Choose **Report a vulnerability** to open a private security advisory.
3. Describe the issue with enough detail to reproduce it — the exact `gmlw` command, the
   client, and what you observed versus expected.

If GitHub's private reporting is unavailable to you, report the repository to GitHub via
https://docs.github.com/en/site-policy/github-terms/reporting-abuse.

## What the wrapper actually does

`generic-ml-wrapper` is a local, single-user tool that **launches ML coding clients
itself** (claude, cursor, codex, vibe) as child processes, and — for metered clients —
runs a local proxy between the client and its upstream API to record token usage. It is
not a sandbox. Understanding its real trust boundaries is the point of this document.

(The sibling [`generic-ml-cache`](https://github.com/danielslobozian/generic-ml-cache)
is a record/replay cache the optional context compressor talks to — it is *not* the
launcher, and it holds none of the wrapper's state.)

### 1. Credentials at rest, and child-process injection

Per-workflow credentials are stored locally in `~/.gmlw/credentials.toml`, written
`0600` (owner read/write only) via an atomic, symlink-safe write; a corrupt file is
never overwritten. At launch the wrapper **injects these values into the child client's
environment** so the client can use them. Consequently:

- The secrets live on your disk and in the launched client's process environment. Anyone
  who can read your home directory or your process environment (root, or you) can read
  them. This is inherent to injecting env vars into a subprocess.
- The wrapper never sends credentials through a model call, and never writes them to the
  ledger, logs, context, or transcript. A token surfacing in any of those is **in scope**
  — report it.

### 2. `config.toml` is a trusted-code boundary

`~/.gmlw/config.toml` can name Python to load and run: `[callers]` (a client-caller
class) and `[[interceptors]]` (context/wire transforms) are resolved by `spec_loader`,
which **imports and executes that code with your full permissions**. This is a
legitimate plugin extension point, not a defect — but it means:

> Only add `[callers]` / `[[interceptors]]` specs you wrote or trust. They run as you.

We deliberately do **not** add a permission check on `config.toml`: anyone who can write
your `~/.gmlw` already has code execution as you by countless other paths (`.bashrc`,
cron, `PATH`), so such a check would be security theater. Instead, `~/.gmlw` is created
owner-only (`0700`), and a configured-but-unloadable spec fails loudly rather than
silently doing nothing.

### 3. The metering relay: outbound traffic and the loopback key

For a metered client the wrapper starts a proxy on `127.0.0.1:<ephemeral>` and points
the client's base URL at it; the proxy **forwards the client's requests over HTTPS to
the real upstream** (e.g. `api.anthropic.com`, `chatgpt.com`, the Mistral/OpenAI
endpoints). So outbound network traffic to those providers is the core function — the
wrapper is not "offline," and the same data the client would send goes upstream.

The proxy is guarded by a **capability URL**: its address is
`http://127.0.0.1:<port>/<client>/<token>`, where `token` is a fresh
`secrets.token_urlsafe(16)` minted per run and is the sole auth boundary — a request
without the right token is refused, and requests carrying a browser `Origin` header are
rejected.

**Disclosure — the token does not seal your API key.** A metering proxy is an HTTP
sidecar, so on the loopback hop the client's request (including its `Authorization` /
API key) reaches `127.0.0.1` in **cleartext** before the proxy re-establishes HTTPS to
the upstream. That cleartext is visible to root and to your own user on the same
machine, and the capability token itself lives in the client's environment
(`ANTHROPIC_BASE_URL` and equivalents) — the same process tree that already holds the
key. The token stops *other local processes and web pages* from driving your proxy; it
does not hide the key from someone who can already read your loopback traffic or your
process environment.

### 4. Transcript data at rest (opt-in)

The transcript feature is **off by default** (`[transcript]`). When enabled, every
metered call's full request, raw response, and usage are written under
`~/.gmlw/transcripts/<job>/<session>/` (owner-only). These files can contain the entire
content of your prompts and the model's responses. Enable it only where storing that
content on disk is acceptable, and treat the folder as sensitive.

### 5. Filesystem containment

All wrapper state lives under `~/.gmlw` (created `0700`). Job identifiers are validated
at the CLI boundary (letters/digits/`-`/`_`, no separators or `..`) and the stores apply
a containment check, so a crafted job id cannot make the wrapper write outside its home
(CWE-22). The wrapper also edits the client's own status-line settings
(`~/.claude/settings.json`, `~/.cursor/cli-config.json`); it refuses to overwrite one it
cannot parse (so it can never destroy your existing settings) and writes atomically.

## Scope

**Expected behavior, not a vulnerability:** "my own `config.toml`, workflow, or
credential made the wrapper run/send something." Those are the trusted-code and
trusted-config boundaries above — you are configuring your own machine.

**In scope — please report:**

- A credential appearing in the ledger, logs, context, transcript, or a model prompt.
- The wrapper writing outside `~/.gmlw` (or destroying a client settings file it should
  have refused to touch).
- The metering proxy forwarding for a process that is not our launched client (an auth
  bypass beyond the disclosed loopback-cleartext reality).
- Any other defect in the engine itself — as opposed to your own configuration — that
  breaks one of the boundaries described here.
