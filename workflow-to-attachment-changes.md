# Workflow → attachment: change list

The work that takes gmlw from workflows to attachments, as specified in
[docs/ATTACHMENTS.md](docs/ATTACHMENTS.md). All of it lands on one branch,
`feature/attachments`, as one PR. Each phase is one or more commits that leave
`nox -s green` passing; tick an item in the commit that does it. This file is deleted in
the last phase.

Scan baseline (2026-10-08): "workflow" appears on 2,248 lines in 100 files: 1,076 in
`src`, 815 in `tests`, 230 in `docs`.

## Decisions to confirm before coding

Confirmed 2026-10-08.

- [x] **D1 `gmlw run` goes.** Its point was "the job is named after the workflow". A
      session gets its attachment with `gmlw start <job> --attach <name>[@<version>]`.
- [x] **D2 No YAML dependency.** `manifest.yaml` is read by a small parser for flat
      `key: value` lines only (the four keys). Anything else in the file is refused.
- [x] **D3 `workflow-creator` source** lives in the repo as a plain folder with its
      `manifest.yaml`; gmlw zips it from the package resources and imports it on install
      and upgrade, skipping a version already stored.
- [x] **D4 Migrated workflows.** Each `~/.gmlw/workflows/<name>/` becomes `<name>@1.0.0`
      with `main_md_file: workflow.md`; today's `_common/base.md` is prepended to that
      file during the migration, so the attachment behaves as the workflow did.
- [x] **D5 One compile mode for attachments.** Modes become `default` and `attachment`;
      `[startup.workflow]` and `[startup.authoring]` config tables are read as
      `[startup.attachment]` (workflow first) until the home migration rewrites them.
- [x] **D6 Authoring separation goes.** A modify or creation session is an ordinary job:
      it shows in `gmlw jobs` and its spend is that job's.

## Phase 0 — Spec

- [x] Commit `docs/ATTACHMENTS.md`, delete the draft `docs/ENGINE_PACKAGE.md`
      (never committed), open the docs PR. (#123)

## Phase 1 — Domain

- [x] `domain/model/attachment.py`: `AttachmentVersion` (`MAJOR.MINOR.PATCH`, no leading
      zeros, ordered number by number), `Attachment` (name, version, description,
      main file, hash).
- [x] `identifiers.py`: `AttachmentName` (same rule as `WorkflowName`, which goes in
      phase 7); i18n `error.identifier.attachment_name`, `error.attachment.version`.
- [x] Tests: version parsing, refusals (`2`, `2.1`, `v1.0.0`, `1.0.0-beta`, `1.02.0`),
      ordering (`2.10.0` > `2.9.0`), highest-version selection.

## Phase 2 — Store and import

- [x] `paths.ATTACHMENTS = HOME / "attachments"`.
- [x] Manifest reader (D2): `name`, `description`, `version`, `main_md_file`; the main
      file must exist in the zip.
- [x] Zip import: unzip to a temporary folder, refuse `..`, absolute paths and links;
      stop if `name@version` exists; move into `attachments/<name>/<version>/`; make
      read-only.
- [x] Folder hash: SHA-256 over sorted relative paths and their bytes.
- [x] Ledger migration 7: table `attachments` (name, version, description, main_md_file,
      hash, imported_at; key name+version). `SCHEMA_VERSION = 7`, final schema updated.
- [x] Port `AttachmentStorePort` + filesystem/SQLite adapter: import, list, get,
      delete, verify (recompute the hash, compare with the ledger).
- [x] Export: write a stored version back as `<name>-<version>.zip`.
- [x] Use cases: `ImportAttachment`, `ExportAttachment`, `ListAttachments`,
      `DeleteAttachment`.
- [x] Tests: import happy path, existing version stops, escapes refused, bad manifest,
      missing main file, hash mismatch marks invalid, delete, export round-trip, migration
      7 from v6.

## Phase 3 — CLI for the store

- [x] `gmlw attachment import <zip>`, `export <name> [<version>]`, `list`,
      `delete <name> <version>`.
- [x] i18n keys (en, fr); `docs/CLI.md` (the docs test requires every command).
- [x] Tests in `test_cli.py`.

## Phase 4 — Attaching to a session

Done additively: workflows keep working until phase 7 removes them, so the renames that
would break them moved there.

- [x] `StartJobCommand.attachment` + `attachment_version`; defaults to the highest; an
      invalid version is refused before a session is recorded. (`workflow` goes in
      phase 7.)
- [x] `CompileMode.ATTACHMENT` with its `[startup.attachment]` defaults. The main file is
      delivered as written, never compressed, so it needs no context source.
- [x] Compile: the attachment section last, through its own interceptor target, after
      gmlw's groups; gmlw's introduction gives name, version, absolute folder and "paths
      are relative to this folder" (`domain/service/attachment_context.py`).
- [x] Callers: `RunContext.extra_dirs`, opened with `--add-dir` on claude (ahead of any
      positional), codex (after `resume <id>`), vibe; on start and on resume. cursor has
      no such flag: documented in `docs/CLIENTS.md`.
- [x] Opening message naming the attachment and version.
- [x] Credentials resolved by attachment name (same store; renamed in phase 8).
- [x] Ledger migration 8: `sessions.attachment`, `attachment_version`, `attachment_hash`;
      `Session`, `sqlite_session_store`; `gmlw sessions` and the TUI show `name@version`.
- [x] Interceptor target `attachment`; seeded config comments.
- [x] `gmlw start --attach NAME[@VERSION]`, exclusive with `--workflow`; `docs/CLI.md`.
- [x] Tests: `test_start_job_usecase`, `test_callers`, `test_filesystem_workflow_source`,
      `test_sqlite_session_store`, `test_list_sessions_usecase`, `test_ledger_migration`,
      `test_cli`.

## Phase 5 — The provided attachment

- [x] `resources/attachments/workflow-creator/` (1.0.0): `manifest.yaml`, `main.md`,
      `guided.md` (read only when the user picks the guided way), `run-conventions.md`
      (today's `_common/base.md`, copied into every workflow it writes). It writes the
      workflow as `<name>/` in the job's folder with its manifest, zips it with
      `manifest.yaml` at the root, and hands over `gmlw attachment import`; a new
      version starts from `gmlw attachment export`. The old
      `resources/workflows/create-workflow/` stays until phase 7.
- [x] Every start imports a provided version the store lacks (D3), through
      `ImportAttachment`; a failure is logged, never fatal (`bootstrap.py`,
      `install_provided_attachments.py`, `packaged_attachments.py`).
- [x] Tests: the shipped manifest is valid and its main file points only at files it
      carries; imported once; a new provided version lands beside the old; bootstrap
      survives a broken one. `docs/ATTACHMENTS.md` §7 says when it is imported.

## Phase 6 — TUI

- [x] Top menu: **Attachments** (import, export, list, delete, modify), above Quit for
      now; phase 7 puts it where Workflow is, which keeps the tests' row counts.
- [x] New-session flow: the attach step offers "Nothing attached", each attachment by
      name, then the workflows; several versions ask which, highest first; a changed
      version is shown, not pickable.
- [x] Modify: opens Job → New with `modify_<name>_v<version>` (dots become `-`, a job id
      has none), the attach step available, and `StartJobCommand.note` adding the
      request to export that version here and help change it.
- [x] Wiring: `Shelf` closures in `app.py` over the real use cases; TUI launches carry
      attachment, version and note.
- [x] Tests in `test_tui_menu.py`, `test_cli.py`, `test_start_job_usecase.py`;
      `docs/CLI.md` tui section.

## Phase 7 — Removal

- [x] CLI: the `workflow` group, `run`, `--workflow`, `--guided`/`--quick` and their
      handlers; `creds set <attachment> <NAME>`; the capability index and the help
      topics (`job-vs-attachment` replaces `job-vs-workflow` and `start-vs-run`).
- [x] Use cases, ports, models and adapters of workflows, drafts and archives; the
      terminal choosers; `WorkflowName`; `resources/workflows/`; `paths.WORKFLOWS`,
      `DRAFTS`, `AUTHORING`, `WORKFLOW_BACKUPS`; their wiring.
- [x] The context composition moved out of the workflow source into
      `FilesystemContextCompiler` behind `ContextCompilerPort`; `StartJobUseCase` takes
      `contexts`. Modes are `default` and `attachment`; `BASE`/`STEPS`, the `technical`
      compressor kind, `includes_workflow`, `[startup.workflow]`/`[startup.authoring]` and
      the `workflow` interceptor target are gone. Resume errors are `error.resume.*`.
- [x] `Session.workflow`, `SessionSummary.workflow`, `SessionChoice.workflow` →
      `attachment`. Ledger migration 9 copies an old session's workflow name into its
      attachment (no version, no hash) and turns authoring jobs into ordinary jobs; the
      old column stays as history.
- [x] Credentials are keyed by attachment name; the file's format is unchanged, so a
      migrated workflow keeps its credentials as they are.
- [x] TUI: Attachments in Workflow's place; the Workflow screens, `Archiver`,
      `ImportAttempt`, `MenuApp.workflows`; the attach step offers attachments only.
- [x] i18n: 98 unused workflow keys removed; the rest reworded (en, fr).
- [x] Wording: rules directive ("per-attachment rule"), greeting, snapshot, seeded
      config, context file and opening, package docstring.
- [x] Tests: workflow-only tests removed with their code; the rest rewritten
      (`test_filesystem_context_compiler.py` is the old source's test file).

## Phase 8 — Home folder migration

- [ ] One-time, idempotent, on first run of the new version: import each
      `~/.gmlw/workflows/<name>/` as `<name>@1.0.0` (D4); rewrite
      `[startup.workflow]`/`[startup.authoring]` and the `workflow` interceptor target in
      `config.toml`; leave `workflows/`, `drafts/`, `authoring/`, `workflow-backups/` in
      place and say they can be deleted. (Credentials need nothing: same file, same keys.)
- [ ] Tests on a fixture home.

## Phase 9 — Docs

- [x] `docs/WORKFLOWS.md` removed; every link to it points to `docs/ATTACHMENTS.md`, which
      is now the user-facing page (no longer a draft) and gains credentials, scripts, and
      "Coming from an older gmlw".
- [x] `docs/CLI.md` (`run`, `workflow`, `--workflow` gone; `creds`, `help`, `tui`),
      `DESIGN.md`, `CONFIGURATION.md` (two modes, no `base`/`steps`/`technical`),
      `USER_GUIDE.md`, `CONCEPTS.md`, `TROUBLESHOOTING.md`, `CLIENTS.md`, `docs/README.md`.
- [x] `docs/tapes/`: the seed imports a demo attachment; `tui.tape` walks Attachments →
      List; `help.tape` shows `job-vs-attachment`. The GIFs are not re-rendered here (no
      `vhs` at first); rendered in the next commit.
- [x] `README.md`, `SECURITY.md`, `GOVERNANCE.md`; `ROADMAP.md`'s parked item. Released
      versions' entries keep their words. `AGENTS.md`'s "pr-hygiene workflow" is a GitHub
      Actions workflow and stays.
- [x] `CHANGELOG.md` `[Unreleased]`: attachments (Added, replacing the unreleased "workflow
      from the menu" entry), the migration (Changed), the removed commands (Removed).

## Phase 10 — Guard and close

- [ ] Test: search `src`, `tests`, `docs` case-insensitively for "workflow"; fail on any
      hit outside `resources/attachments/workflow-creator/`, the ledger's past migrations,
      and the guard test itself.
- [ ] Delete this file.
