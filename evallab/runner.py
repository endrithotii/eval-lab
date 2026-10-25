"""Run one model with one prompt version over a suite, resumably."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone

from .llm import Model, QuotaExhausted
from .scorers import score_case
from .store import Store


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def run_id(suite: dict, model: Model, prompt: str) -> str:
    """Same inputs, model and prompt text give the same run id, so a run resumes instead of restarting.
    The answer key is left out on purpose: fixing it means re-scoring, not paying for new model calls."""
    inputs = [[c["id"], c["input"]] for c in suite["cases"]]
    return f"{suite['name']}:{model.name}:{prompt}:{_hash([inputs, suite['prompts'][prompt]])}"


def rescore(suite: dict, store: Store) -> int:
    """Apply the current answer key and scorers to every stored answer of this suite."""
    cases, n = {c["id"]: c for c in suite["cases"]}, 0
    for r in store.runs(suite["name"]):
        for cid, a in store.answers(r["id"]).items():
            if cid in cases and not a["error"]:
                scores = score_case(suite["fields"], cases[cid]["expected"], a["output"])
                store.save_answer(r["id"], cid, a["output"], scores, a["latency_ms"], a["tokens_in"], a["tokens_out"])
                n += 1
    return n


def run(suite: dict, model: Model, prompt: str, store: Store, note: str = "") -> dict:
    rid = run_id(suite, model, prompt)
    store.start_run({"id": rid, "suite": suite["name"], "suite_hash": _hash(suite["cases"]), "model": model.name,
                     "prompt": prompt, "prompt_hash": _hash(suite["prompts"][prompt]),
                     "started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "note": note})
    done = store.answered(rid)
    p = suite["prompts"][prompt]
    stopped = None
    for case in suite["cases"]:
        if case["id"] in done:
            continue
        t0 = time.monotonic()
        try:
            out = model.complete_json(p["system"], p["user"].format(**case["input"]))
            err = None
        except QuotaExhausted as e:
            stopped = str(e)
            break
        except Exception as e:  # a failed case is recorded, and retried on the next run
            out, err = None, f"{type(e).__name__}: {e}"
        ms = int((time.monotonic() - t0) * 1000)
        usage = getattr(model, "last_usage", None) or {}
        scores = score_case(suite["fields"], case["expected"], out) if err is None else {}
        store.save_answer(rid, case["id"], out, scores, ms, usage.get("input", 0), usage.get("output", 0), err)
        print(f"  {case['id']}: {' '.join(f'{k}={v}' for k, v in scores.items()) or err}", file=sys.stderr, flush=True)
    complete = stopped is None and len(store.answered(rid)) == len(suite["cases"])
    store.finish_run(rid, datetime.now(timezone.utc).isoformat(timespec="seconds"), complete)
    return {"run_id": rid, "complete": complete, "stopped": stopped}
