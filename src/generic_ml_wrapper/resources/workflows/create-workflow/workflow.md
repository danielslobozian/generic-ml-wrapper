# create-workflow

*The meta-workflow: it interviews the user about a task they do repeatedly, then
writes a new workflow into its folder so the wrapper can run it later. The new
workflow's folder is your working directory — write the new files there.*

## How to interview — be a warm, active listener

You are having a relaxed conversation about how someone works, not filling in a
form. Draw out what they know without making them structure it for you.

- **Open the door.** Say this is a relaxed chat, there are no wrong answers, and
  they can go at their own pace. Then ask your first question.
- **One question at a time.** Ask, listen to the whole answer, follow their
  thread, then ask the next.
- **Keep a running summary visible.** After each meaningful answer, show a short
  "What I've captured so far" block so the user always sees the workflow taking
  shape and can correct it as you go.

## Steps

### 1. Understand the task
Ask what the workflow is for, walk through how they do it today start to finish,
what "done" looks like, and what they always check.

### 2. Draft the steps — and mark what can be code
Turn their answer into a lean, ordered list. Each step has a clear purpose and a
concrete output. Resist adding steps they didn't describe.

Then judge each step's nature and show the draft as a table with a **Code?** column:

| # | Step | Output | Code? |
|---|------|--------|-------|
| 1 | …    | …      | ✅ scriptable / ⚠️ partly / ❌ needs judgment |

A step is **scriptable** when it is deterministic and mechanical — parsing,
formatting, file moves, computations, or calling an API with fixed logic. It is
**not** scriptable when it needs judgment, taste, or reading intent — reviewing tone,
choosing an approach, drafting prose. Most workflows are a mix; be honest about which
is which. Not every step can be code.

### 3. Offer to script the mechanical steps
For each ✅/⚠️ step, **offer** to generate a small script (python or shell) that does
it deterministically, saved under `scripts/` in this folder. A scripted step then
becomes "run `scripts/<name>`" instead of you redoing the reasoning every run —
faster, cheaper, and reliable. Generate a script only where it genuinely simplifies,
get the user's OK first, and leave the judgment steps to the AI.

### 4. Write workflow.md
Write the steps to `workflow.md` in this folder, following the shape of this file
(title, one-line purpose, numbered `## Steps`). For a scripted step, the instruction
is to run its script; for a judgment step, the instruction is what to decide. Revise
until they agree.

### 5. Confirm
Tell the user how to run it, then stop.
