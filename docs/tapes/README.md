# Demo tapes

The README GIFs are generated from these [VHS](https://github.com/charmbracelet/vhs)
`.tape` scripts, so they can be regenerated deterministically whenever the CLI
changes — no manual screen recording.

| Tape | Renders | Shows |
|---|---|---|
| `usage.tape` | `docs/images/gmlw-usage.gif` | `gmlw jobs` → `sessions` → `export` — the job read-back |
| `statusline.tape` | `docs/images/gmlw-statusline.gif` | the status line the wrapper renders (git · folder · model · context · live cost) |

## Regenerate

```sh
uv sync --extra dev        # so `gmlw` is on PATH (or set GMLW_BIN=/path/to/gmlw)
docs/tapes/render.sh
```

`render.sh` seeds a throwaway ledger (`seed.py`) and a demo git repo in a
temporary `$HOME` — it never touches your real `~/.gmlw` — then renders both
tapes. No client is launched and no network call is made; the demos exercise
only the read/render paths.

Requires `vhs`, `ffmpeg`, and `git`.
