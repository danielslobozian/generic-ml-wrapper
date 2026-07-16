# Clients

`gmlw` drives four coding CLIs behind one surface: `--client claude | cursor | codex | vibe`
(default set by `[client] default` in config). The commands you run — `gmlw start`,
`gmlw jobs`, `gmlw export` — are identical whichever client you pick. But the clients are
not identical. What the wrapper can meter, resume, render into a status line, or deliver
context through depends entirely on the underlying tool's API and CLI. This page is the
per-client truth.

Each caller declares three capability flags — `can_meter_per_call`, `can_resume`,
`can_deliver_statusline` — and the wrapper adapts to them. Read the matrix, then the
section for the client you use.

## Capability matrix

| Client | Binary | Metering | Resume | Status line | Context delivery |
| ------ | ------ | -------- | ------ | ----------- | ---------------- |
| claude | `claude` | Yes — Anthropic SSE | Yes | Yes | Native `--append-system-prompt-file` + `--session-id` |
| cursor | `cursor-agent` | **No** | Yes | Yes | Context-file instruction; status-line install only, no relay |
| codex | `codex` | Yes — OpenAI Responses | **No** | No | Initial instruction; relay → `chatgpt.com/backend-api/codex` |
| vibe | `vibe` | Yes — Mistral / Chat Completions | **No** | No | Initial instruction; throwaway `VIBE_HOME` repointed at the relay |

You install and log into each client yourself. `gmlw` is not a sandbox and ships no
credentials — it launches the real binary with your own login and environment. See
[../SECURITY.md](../SECURITY.md).

## claude

**Binary:** `claude`. Install Claude Code and sign in yourself first; `gmlw` invokes the
`claude` binary on your `PATH` with your existing login.

**Metering:** Full per-call metering. Requests route through the local relay and the
wrapper reads Anthropic's streaming (SSE) usage, writing per-turn tokens (including cache)
and cost to the ledger. `gmlw export <job>` reports it.

**Resume:** Supported. The wrapper binds the session by passing `--session-id`, so
`gmlw start <job> --resume-latest` continues the most recent session.

**Status line:** Supported. `gmlw` installs a status-line hook into `~/.claude/settings.json`
(it refuses to overwrite an unparseable file and writes atomically). Claude then calls
`gmlw statusline`, whose output is produced by the Claude status parser. You do not run
`gmlw statusline` by hand.

**Context delivery:** Native. Compiled context (workflow blob or startup context) is written
to a context file and passed with `--append-system-prompt-file`, leaving a durable
provenance artifact under `~/.gmlw/contexts/`.

## cursor

**Binary:** `cursor-agent`. Install the Cursor CLI and log in yourself first.

**Metering:** **Not metered by the OSS wrapper.** Cursor's usage does not travel over an
interceptable API the wrapper can sit in front of, so `can_meter_per_call` is false and no
relay is started for cursor. `gmlw jobs` / `gmlw export` will show sessions but no token or
cost figures for cursor runs. If you need metering, use claude, codex, or vibe.

**Resume:** Supported.

**Status line:** Supported — install only. `gmlw` writes the status-line configuration into
`~/.cursor/cli-config.json` (same atomic, refuse-if-unparseable handling as claude), and
Cursor's payload is read by the Cursor status parser. Because nothing is metered, the status
line reflects only what Cursor itself reports.

**Context delivery:** Context is delivered as an instruction pointing at the compiled context
file. There is no relay in the cursor path.

## codex

**Binary:** `codex`. Install the Codex CLI and sign in yourself first.

**Metering:** Full per-call metering via the OpenAI Responses endpoint. The wrapper starts
the local relay and points codex's upstream at it (`/backend-api/codex` on
`chatgpt.com`), teeing the response to read usage. Per-turn tokens and cost land in the
ledger.

**Resume:** **Not supported.** `can_resume` is false — the wrapper cannot bind or resume a
codex session by its own id. Every `gmlw start` on a codex job is a fresh session;
`--resume-latest` has nothing to attach to.

**Status line:** **Not supported.** Codex has no status-line surface the wrapper can install
into, so no live `gmlw statusline` output during codex runs. Metering is still recorded — use
`gmlw export <job>` after the fact.

**Context delivery:** Context is delivered as an initial instruction at launch (not a native
system-prompt file). Requests then flow through the relay to the Responses endpoint.

## vibe

**Binary:** `vibe` (Mistral's CLI). Install it and log in yourself first.

**Metering:** Full per-call metering via Mistral / Chat Completions. The wrapper starts the
relay and, because vibe has no flag to repoint one provider, writes a **throwaway
`VIBE_HOME`** whose config repoints the provider at the relay for the duration of the run.
The throwaway home is removed when the run ends. Per-turn tokens and cost are recorded.

**Resume:** **Not supported.** `can_resume` is false — the wrapper cannot bind or resume a
vibe session by its own id, and the throwaway `VIBE_HOME` holds no durable session state.
Each run is fresh; `--resume-latest` does not apply.

**Status line:** **Not supported.** No status-line surface; rely on `gmlw export <job>` for
the numbers.

**Context delivery:** Context is delivered as an initial instruction at launch, through the
same throwaway-`VIBE_HOME` relay path used for metering.

## Choosing a client

- **Want metering and resume and a live status line?** Use **claude** — it is the only client
  that supports all three.
- **Want resume and a status line but don't need wrapper metering?** **cursor** works, with the
  clear caveat that cost/token numbers won't be captured.
- **Want metering on OpenAI or Mistral models?** **codex** or **vibe** meter fully, but each
  run is a fresh session (no resume) and there is no status line — read costs with
  `gmlw export`.

## Known limitations

- **Cursor is not metered.** Its usage isn't on an interceptable API; cursor runs have no
  token or cost figures.
- **Codex does not resume.** No session-id binding; `--resume-latest` has nothing to attach to.
- **Vibe does not resume.** Throwaway `VIBE_HOME` keeps no durable session; every run is fresh.
- **Codex and vibe have no status line.** Use `gmlw export <job>` for their numbers instead.
- **Not a sandbox.** Every client runs as you, with your credentials; on the loopback relay hop
  the client's API key is briefly in cleartext to you/root before HTTPS is re-established
  upstream. See [../SECURITY.md](../SECURITY.md).

## See also

- [CONFIGURATION.md](CONFIGURATION.md) — `[client] default`, `[callers]`, interceptors, and
  the startup context matrix.
- [WORKFLOWS.md](WORKFLOWS.md) — how compiled context and workflows are assembled and injected.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — when a client won't launch, meter, or render.
- [CLI.md](CLI.md) — every `gmlw` command.
- [DESIGN.md](DESIGN.md) — the caller model and metering relay in depth.
- [../SECURITY.md](../SECURITY.md) — the trust and credential boundary.
</content>
</invoke>
