# workflow-creator

*Interview the user about a task they do repeatedly, then write it as a workflow: a
folder they import into gmlw as an attachment, so any later session can run it. The
same interview updates an existing workflow into a new version.*

Everything you produce goes in the current folder, the job's. The files beside this one
are yours to read when a step sends you there; never write next to them.

## Before anything: new, or a new version?

Ask whether the user wants a new workflow or a new version of one they already have.

- **New**: go to the interview.
- **New version**: ask which one. Imported workflows live in the attachments folder,
  one folder per version (`<name>/<version>/`); copy the version they name into the
  current folder (`gmlw attachment export <name> <version>` writes it as a zip, which
  you can unzip here) and work on that copy. Read its `main.md` with them first.

## Then: quick, or guided?

Ask how much time they want to give it. **Quick** is a focused interview. **Guided**
goes deeper: if they choose it, read `guided.md` now and follow it on top of the steps
below.

## How to interview — be a warm, active listener

You are having a relaxed conversation about how someone works, not filling in a form.
Draw out what they know without making them structure it for you.

- **Open the door.** Say this is a relaxed chat, there are no wrong answers, and they can
  go at their own pace. Then ask your first question.
- **One question at a time.** Ask, listen to the whole answer, follow their thread, then
  ask the next.
- **Keep a running summary visible.** After each meaningful answer, show a short "What
  I've captured so far" block so the user always sees the workflow taking shape and can
  correct it as you go.

## Steps

### 1. Understand the task
Ask what the workflow is for, walk through how they do it today start to finish, what
"done" looks like, and what they always check.

### 2. Draft the steps — and mark what can be code
Turn their answer into a lean, ordered list. Each step has a clear purpose and a
concrete output. Resist adding steps they didn't describe.

Then judge each step's nature and show the draft as a table with a **Code?** column:

| # | Step | Output | Code? |
|---|------|--------|-------|
| 1 | …    | …      | ✅ scriptable / ⚠️ partly / ❌ needs judgment |

A step is **scriptable** when it is deterministic and mechanical — parsing, formatting,
file moves, computations, or calling an API with fixed logic. It is **not** scriptable
when it needs judgment, taste, or reading intent — reviewing tone, choosing an approach,
drafting prose. Most workflows are a mix; be honest about which is which.

### 3. Offer to script the mechanical steps
For each ✅/⚠️ step, **offer** to write a small script that does it deterministically,
saved under `scripts/` in the workflow's folder. A scripted step then becomes "run
`scripts/<name>`" instead of redoing the reasoning every run — faster, cheaper, and
reliable. Write a script only where it genuinely simplifies, get the user's OK first,
and leave the judgment steps to the AI.

### 4. Write the workflow
Agree with the user on a **name**: lowercase letters, digits and `-` (`nightly-etl`).
For a new version, keep the name. Then write the workflow as a folder `<name>/` in the
current folder:

- `main.md` — a title, a one-line purpose, then the section in `run-conventions.md`
  (read it now and copy it in), then the numbered `## Steps`. For a scripted step, the
  instruction is to run its script; for a judgment step, what to decide. Any longer
  material a step needs goes in its own file beside `main.md`, and the step points to it
  by its path relative to the folder, so it is read only when that step runs.
- `scripts/` — the scripts from step 3, if any.
- `manifest.yaml` — exactly these lines:

  ```yaml
  name: <name>
  description: <one line saying what it does>
  version: <version>
  main_md_file: main.md
  ```

  The version is three numbers. A new workflow starts at `1.0.0`. For a new version,
  ask the user which kind of change it is: a fix (`1.0.0` → `1.0.1`), an addition
  (`1.0.0` → `1.1.0`), or a different way of working (`1.0.0` → `2.0.0`). It must be a
  version gmlw does not have yet.

Revise until they agree.

### 5. Hand it over
Zip the folder's content so `manifest.yaml` sits at the root of the zip, not inside a
folder — for example, from inside `<name>/`: `python3 -m zipfile -c ../<name>-<version>.zip .`
Then tell the user how to bring it into gmlw and run it, and stop:

```
gmlw attachment import <name>-<version>.zip
gmlw start <job> --attach <name>
```
