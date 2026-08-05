"""Seed a demo ~/.gmlw ledger for the README demo GIFs. No secrets, no network."""

import sys
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStoreAdapter
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStoreAdapter
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStoreAdapter
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

home = Path(sys.argv[1]) / ".gmlw"
home.mkdir(parents=True, exist_ok=True)

# Mark the demo home as already past `gmlw init` (added in 0.4.0) -- without this,
# every real command (jobs/sessions/export) hits the forced first-run gate and blocks
# on an interactive prompt instead of rendering. `statusline` and `help` are exempt
# from the gate, so this only matters for the read commands the tapes actually run.
(home / "config.toml").write_text(
    '[init]\nversion = "1.0.0"   # demo-seeded; real value is written by `gmlw init`\n',
    encoding="utf-8",
)

ledger = Ledger(home / "ledger.db")
sessions = SqliteSessionStoreAdapter(ledger, kind="work")
turns = SqlitePerTurnStoreAdapter(ledger)
costs = SqliteUsageStoreAdapter(ledger)

JOB = "REFACTOR-42"
# A fixed base epoch so the rendered HH:MM:SS is deterministic across renders.
T = 1_732_020_000  # ~a mid-afternoon local time
data = [
    ("REFACTOR-42_001", "uuid-1", [
        TurnUsage("REFACTOR-42_001", 18240, 1120, 0.0912, "Opus 4.8", cache_read_tokens=12000, timestamp=T + 0, duration_s=7.4, turn_id="req_a1f3"),
        TurnUsage("REFACTOR-42_001", 6300, 840, 0.0361, "Opus 4.8", cache_read_tokens=4200, timestamp=T + 71, duration_s=4.1, turn_id="req_b7c2"),
    ], 0.1273),
    ("REFACTOR-42_002", "uuid-2", [
        TurnUsage("REFACTOR-42_002", 9800, 2360, 0.0642, "Sonnet 5", cache_read_tokens=5100, timestamp=T + 1840, duration_s=5.6, turn_id="req_c9e4"),
    ], 0.0642),
    ("REFACTOR-42_003", "uuid-3", [
        TurnUsage("REFACTOR-42_003", 21400, 3050, 0.1740, "Opus 4.8", cache_creation_tokens=8000, cache_read_tokens=9000, timestamp=T + 3600, duration_s=11.2, turn_id="req_d2a8"),
        TurnUsage("REFACTOR-42_003", 4100, 260, 0.0208, "Opus 4.8", cache_read_tokens=3000, timestamp=T + 3702, duration_s=2.3, turn_id="req_e5b1"),
    ], 0.1948),
]
for sid, uuid, sturns, cost in data:
    sessions.record(Session(sid, JOB, "claude", uuid))
    for t in sturns:
        turns.record(JOB, t)
    costs.record_session_cost(JOB, sid, cost)

# A demo workflow, so the TUI's Workflow > List browser has something to show (matches
# the worked example in docs/WORKFLOWS.md).
workflow_dir = home / "workflows" / "doc-review"
workflow_dir.mkdir(parents=True, exist_ok=True)
(workflow_dir / "workflow.md").write_text(
    "# doc-review\n\n"
    "*Review a documentation change for clarity and correctness before it ships.*\n\n"
    "## Steps\n\n"
    "### 1. Collect the changed docs\n"
    "Run `scripts/collect.sh` to list the docs touched on this branch and gather their diffs.\n\n"
    "### 2. Review clarity and accuracy\n"
    "Read each changed doc. Flag anything unclear, out of date, or contradicted by the code.\n\n"
    "### 3. Report and stop\n"
    "Summarise the findings as a short checklist the author can act on, then stop.\n",
    encoding="utf-8",
)
(workflow_dir / ".about.toml").write_text(
    'label = "Doc review"\ndescription = "Review a documentation change before it ships."\n',
    encoding="utf-8",
)

print(f"seeded {home/'ledger.db'} — job {JOB}, {len(data)} sessions, 1 workflow")
