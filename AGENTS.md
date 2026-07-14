# AGENTS.md — working rules for this repo

Rules an automated or human contributor must follow. Where a rule can be a
runnable gate it is one (see `.pre-commit-config.yaml` and `noxfile.py`); prose
here is the intent behind those gates.

## Process

- **Never commit directly to `main`.** Work on a branch named
  `feature/… tech/… fix/… release/… docs/… chore/… test/…`. Enforced by
  `tools/hooks/guard-branch.sh`.
- **`nox -s green` must pass before every commit** — ruff (lint + format), import
  contracts, pyright strict, tests + coverage floor. The gate that runs locally is the
  one CI runs. `main` requires the `ci` and `no AI attribution` checks (branch protection).
- **Keep changes small and cohesive**, each landing with its tests and leaving the gate
  green. The pipeline is never red.
- **No AI/assistant attribution** in commit messages or PRs. Enforced locally by
  `tools/hooks/check-commit-msg.sh` and server-side by the `pr-hygiene` workflow.

## Architecture

- The design is `docs/DESIGN.md`; do not re-derive it. Follow the hexagon:
  **dependencies point inward** (domain ← usecase ← ports; adapters depend on
  ports, never the reverse).
- **Public-clean by construction.** No personal data, employer, internal hosts, or
  private protocols in this repo — real content lives only under `~/.gmlw`. Commit with a
  public identity (a GitHub no-reply address), never a private/work one; the gitignored
  `secret-audit.sh` gates every publish for private terms and secrets.
- **Strict typing.** pyright strict, zero errors, over **both `src/` and `tests/`**,
  pinned to `pyright==1.1.411`. `# type: ignore` only for a provably-safe case that cannot
  be expressed in the type system, with a comment.
