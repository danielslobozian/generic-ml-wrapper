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

- [ ] CLI: the `workflow` group (`new`, `edit`, `resume`, `drafts`, `list`, `import`,
      `export`), `run`, `--workflow`, `--guided`; handlers in `app.py`.
- [ ] Use cases and ports: `new_workflow`, `edit_workflow`, `import_workflow`,
      `export_workflow`, `list_workflows`, `list_workflow_catalog`, `list_drafts`.
- [ ] Models: `workflow.py`, `draft.py`, `archive_status.py` (if unused); `WorkflowName`
      in `identifiers.py` and its i18n key.
- [ ] Adapters: `adapter/outbound/workflow/` (source, zip archive),
      `tty_workflow_chooser.py`, `tty_guided_chooser.py`.
- [ ] `paths.py`: `WORKFLOWS`, `DRAFTS`, `AUTHORING`, `WORKFLOW_BACKUPS`.
- [ ] Moved from phase 4: `StartJobCommand.workflow`; `CompileMode.WORKFLOW`/`AUTHORING`,
      `BASE`/`STEPS`, `includes_workflow`, `[startup.workflow]`/`[startup.authoring]`;
      the `workflow` interceptor target; the workflow kickoff (`start_job.py`) and
      "the workflow steps" in `context_opening.py`; `Session.workflow` and
      `SessionSummary.workflow` (the ledger column stays, as history).
- [ ] `composition.py` wiring.
- [ ] TUI: move Attachments to Workflow's place in the top menu; drop `Archiver`,
      `AttachWorkflowScreen`'s workflow rows, the Workflow screens, `MenuApp.workflows`.
- [ ] `resources/workflows/`.
- [ ] Help topics `job-vs-workflow`, `start-vs-run` (`help_topics.py`), replaced by one
      on attachments.
- [ ] i18n: every `*workflow*`, `tui.wf.*` key (en, fr).
- [ ] Wording in `rules.py`, `greeting.py`, `session_snapshot.py`,
      `filesystem_layout_seeder.py`, `context_file.py`, `__init__.py`.
- [ ] Tests removed with their code: `test_new_workflow_usecase`,
      `test_edit_workflow_usecase`, `test_import_export_workflow_usecase`,
      `test_list_workflows_usecase`, `test_filesystem_workflow_source`,
      `test_workflow_archive`, `test_tty_workflow_chooser`, `test_tty_guided_chooser`,
      `test_authoring_separation`; workflow cases in `test_cli`, `test_tui_menu`,
      `test_domain_errors`, `test_identifiers`, `test_i18n`, `test_exit_handling`,
      `test_delete_jobs_usecase`, `_conformance`.

## Phase 8 — Home folder migration

- [ ] One-time, idempotent, on first run of the new version: import each
      `~/.gmlw/workflows/<name>/` as `<name>@1.0.0` (D4); rename per-workflow credentials;
      rewrite `[startup.workflow]`/`[startup.authoring]` and the `workflow` interceptor
      stage in `config.toml`; leave `workflows/`, `drafts/`, `authoring/`,
      `workflow-backups/` in place and say they can be deleted.
- [ ] Tests on a fixture home.

## Phase 9 — Docs

- [ ] `docs/WORKFLOWS.md` removed; links to it point to `docs/ATTACHMENTS.md`.
- [ ] `docs/CLI.md`, `DESIGN.md`, `CONFIGURATION.md`, `USER_GUIDE.md`, `CONCEPTS.md`,
      `TROUBLESHOOTING.md`, `CLIENTS.md`, `docs/README.md`.
- [ ] `docs/tapes/` (`seed.py`, `tui.tape`, `help.tape`, `render.sh`, `README.md`).
- [ ] `README.md`, `ROADMAP.md`, `SECURITY.md`, `GOVERNANCE.md`, `AGENTS.md`.
- [ ] `CHANGELOG.md` `[Unreleased]`: the change, the migration, the removed commands.

## Phase 10 — Guard and close

- [ ] Test: search `src`, `tests`, `docs` case-insensitively for "workflow"; fail on any
      hit outside `resources/attachments/workflow-creator/`, the ledger's past migrations,
      and the guard test itself.
- [ ] Delete this file.
