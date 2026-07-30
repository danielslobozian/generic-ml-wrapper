# Demo tapes

The README GIFs are generated from these [VHS](https://github.com/charmbracelet/vhs)
`.tape` scripts, so they can be regenerated deterministically whenever the CLI
changes — no manual screen recording.

| Tape | Renders | Shows |
|---|---|---|
| `usage.tape` | `docs/images/gmlw-usage.gif` | `gmlw jobs` → `sessions` → `export` — the job read-back |
| `statusline.tape` | `docs/images/gmlw-statusline.gif` | the status line the wrapper renders (git · folder · model · context · live cost) |
| `help.tape` | `docs/images/gmlw-help.gif` | `gmlw help` → `gmlw help job-vs-workflow` — the built-in concept explainer |
| `tui.tape` | `docs/images/gmlw-tui.gif` | `gmlw tui` — a browse-only tour of Job/Workflow/Config, entering only the read-only List screens |

## Regenerate

```sh
uv sync --extra dev        # so `gmlw` is on PATH (or set GMLW_BIN=/path/to/gmlw)
docs/tapes/render.sh
```

`render.sh` seeds a throwaway ledger + one workflow (`seed.py`) and a demo git
repo in a temporary `$HOME` — it never touches your real `~/.gmlw` — then
renders all four tapes. No client is launched and no network call is made; the
demos exercise only the read/render paths. `tui.tape` only ever enters a
read-only browser screen (Job/Workflow/Config → List) — never New, Resume,
Run, Create, Edit, or a config switcher, any of which would launch a client or
write config.

Requires `vhs`, `ffmpeg`, `git`, and `ttyd` (a VHS dependency).
