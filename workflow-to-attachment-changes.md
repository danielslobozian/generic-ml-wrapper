# Workflow → attachment: change list

The work that takes gmlw from workflows to attachments, as specified in
[docs/ATTACHMENTS.md](docs/ATTACHMENTS.md). Tick an item when it is merged. Each phase is
one or more small PRs that leave `nox -s green` passing. This file is deleted in the last
phase.

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

- [ ] Commit `docs/ATTACHMENTS.md`, delete the draft `docs/ENGINE_PACKAGE.md`
      (never committed), open the docs PR.

## Phase 1 — Domain

- [ ] `domain/model/attachment.py`: `AttachmentVersion` (`MAJOR.MINOR.PATCH`, no leading
      zeros, ordered number by number), `Attachment` (name, version, description,
      main file, hash).
- [ ] `identifiers.py`: `AttachmentName` replaces `WorkflowName` (same rule); i18n
      `error.identifier.attachment_name`.
- [ ] Tests: version parsing, refusals (`2`, `2.1`, `v1.0.0`, `1.0.0-beta`, `1.02.0`),
      ordering (`2.10.0` > `2.9.0`), highest-version selection.

## Phase 2 — Store and import

- [ ] `paths.ATTACHMENTS = HOME / "attachments"`.
- [ ] Manifest reader (D2): `name`, `description`, `version`, `main_md_file`; the main
      file must exist in the zip.
- [ ] Zip import: unzip to a temporary folder, refuse `..`, absolute paths and links;
      stop if `name@version` exists; move into `attachments/<name>/<version>/`; make
      read-only.
- [ ] Folder hash: SHA-256 over sorted relative paths and their bytes.
- [ ] Ledger migration 7: table `attachments` (name, version, description, main_md_file,
      hash, imported_at; key name+version). `SCHEMA_VERSION = 7`, final schema updated.
- [ ] Port `AttachmentStorePort` + filesystem/SQLite adapter: import, list, get,
      delete, verify (recompute the hash, compare with the ledger).
- [ ] Export: write a stored version back as `<name>-<version>.zip`.
- [ ] Use cases: `ImportAttachment`, `ExportAttachment`, `ListAttachments`,
      `DeleteAttachment`.
- [ ] Tests: import happy path, existing version stops, escapes refused, bad manifest,
      missing main file, hash mismatch marks invalid, delete, export round-trip, migration
      7 from v6.

## Phase 3 — CLI for the store

- [ ] `gmlw attachment import <zip>`, `export <name> [<version>]`, `list`,
      `delete <name> <version>`.
- [ ] i18n keys (en, fr); `docs/CLI.md` (the docs test requires every command).
- [ ] Tests in `test_cli.py`.

## Phase 4 — Attaching to a session

- [ ] `StartJobCommand.workflow` → `attachment` (name + optional version); default to
      the highest version; refuse an invalid version.
- [ ] `context_source.py`: `BASE`/`STEPS` → one `ATTACHMENT` source (the main file);
      `CompileMode` → `DEFAULT`, `ATTACHMENT` (D5); drop `includes_workflow`.
- [ ] Compile: main file after gmlw's groups, introduced by gmlw's line (name, version,
      absolute folder, "paths are relative to this folder").
- [ ] Callers: open the store with `--add-dir` on claude, codex, vibe; check what
      cursor offers and document it in `docs/CLIENTS.md`.
- [ ] Opening message naming the attachment and version (replaces the workflow kickoff in
      `start_job.py:203`, and `context_opening.py:25`).
- [ ] Credentials keyed by attachment name (`credentials_store`, `set_credential`,
      `gmlw creds set`).
- [ ] Ledger migration 8 (or folded into 7): `sessions.workflow` → `attachment`, add
      `attachment_version`, `attachment_hash`; `Session`, `sqlite_session_store`,
      `list_sessions`, `gmlw sessions` and the TUI session list show `name@version`.
- [ ] Interceptor stage `workflow` → `attachment` (`interceptor_chain.py`,
      `port/outbound/interceptor.py`, seeded config comments).
- [ ] Config: `[startup.attachment]` (D5) in `config.py`, seeder template.
- [ ] Tests: `test_start_job_usecase`, `test_context_source`, `test_config`, caller
      argv tests, `test_ledger_migration`, `test_sqlite_session_store`.

## Phase 5 — The provided attachment

- [ ] Move `resources/workflows/create-workflow/` to `resources/attachments/workflow-creator/`
      with `manifest.yaml` (1.0.0); fold in what it needs from `_common/base.md` and
      `guided.md`; its text writes its result to the job's folder as a zip-ready folder
      with a manifest.
- [ ] Install and upgrade import it (D3).
- [ ] Tests: the shipped manifest is valid; install imports it once.

## Phase 6 — TUI

- [ ] Main menu: the Workflow entry becomes Attachments: import, export, list, delete,
      modify.
- [ ] New-session flow: pick an attachment (or none), then its version (default highest).
- [ ] Modify: opens the new-job screen named `modify_<name>_v<version>`, attachment
      picker available, opening message asks the client to export that version into the
      job's folder and help change it.
- [ ] Tests in `test_tui_menu.py`.

## Phase 7 — Removal

- [ ] CLI: the `workflow` group (`new`, `edit`, `resume`, `drafts`, `list`, `import`,
      `export`), `run`, `--workflow`, `--guided`; handlers in `app.py`.
- [ ] Use cases and ports: `new_workflow`, `edit_workflow`, `import_workflow`,
      `export_workflow`, `list_workflows`, `list_workflow_catalog`, `list_drafts`.
- [ ] Models: `workflow.py`, `draft.py`, `archive_status.py` (if unused).
- [ ] Adapters: `adapter/outbound/workflow/` (source, zip archive),
      `tty_workflow_chooser.py`, `tty_guided_chooser.py`.
- [ ] `paths.py`: `WORKFLOWS`, `DRAFTS`, `AUTHORING`, `WORKFLOW_BACKUPS`.
- [ ] `composition.py` wiring.
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
