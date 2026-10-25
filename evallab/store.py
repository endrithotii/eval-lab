"""Every run and every answer, in one SQLite file, so history is never lost."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, suite TEXT, suite_hash TEXT, model TEXT, prompt TEXT, prompt_hash TEXT,
  started TEXT, finished TEXT, complete INTEGER, note TEXT
);
CREATE TABLE IF NOT EXISTS answers (
  run_id TEXT, case_id TEXT, output TEXT, scores TEXT, latency_ms INTEGER,
  tokens_in INTEGER, tokens_out INTEGER, error TEXT,
  PRIMARY KEY (run_id, case_id)
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def start_run(self, run: dict) -> None:
        self.db.execute("INSERT OR IGNORE INTO runs VALUES (:id,:suite,:suite_hash,:model,:prompt,:prompt_hash,"
                        ":started,NULL,0,:note)", run)
        self.db.commit()

    def finish_run(self, run_id: str, finished: str, complete: bool) -> None:
        self.db.execute("UPDATE runs SET finished=?, complete=? WHERE id=?", (finished, int(complete), run_id))
        self.db.commit()

    def answered(self, run_id: str) -> set[str]:
        return {r["case_id"] for r in self.db.execute("SELECT case_id FROM answers WHERE run_id=? AND error IS NULL", (run_id,))}

    def save_answer(self, run_id: str, case_id: str, output, scores, latency_ms, tokens_in, tokens_out, error=None):
        self.db.execute("INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?,?,?,?)",
                        (run_id, case_id, json.dumps(output), json.dumps(scores), latency_ms, tokens_in, tokens_out, error))
        self.db.commit()

    def runs(self, suite: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM runs", ()
        if suite:
            q, args = q + " WHERE suite=?", (suite,)
        return [dict(r) for r in self.db.execute(q + " ORDER BY started", args)]

    def answers(self, run_id: str) -> dict[str, dict]:
        out = {}
        for r in self.db.execute("SELECT * FROM answers WHERE run_id=?", (run_id,)):
            d = dict(r)
            d["output"], d["scores"] = json.loads(d["output"]), json.loads(d["scores"])
            out[d["case_id"]] = d
        return out
