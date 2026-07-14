"""Seed a demo ~/.gmlw ledger for the README demo GIFs. No secrets, no network."""

import sys
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStore
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

home = Path(sys.argv[1]) / ".gmlw"
home.mkdir(parents=True, exist_ok=True)
ledger = Ledger(home / "ledger.db")
sessions = SqliteSessionStore(ledger, kind="work")
turns = SqlitePerTurnStore(ledger)
costs = SqliteUsageStore(ledger)

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

print(f"seeded {home/'ledger.db'} — job {JOB}, {len(data)} sessions")
