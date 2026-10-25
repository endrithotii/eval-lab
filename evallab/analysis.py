"""Turn stored answers into numbers: per run, per field, and between two runs."""

from __future__ import annotations

from collections import Counter

from .stats import mcnemar_exact, paired_bootstrap, verdict
from .store import Store

OUTCOMES = ["correct", "wrong", "missed", "hallucinated"]


def summarise(store: Store, suite: dict, run: dict) -> dict:
    answers = store.answers(run["id"])
    fields = list(suite["fields"])
    per_field = {f: Counter() for f in fields}
    case_ok, lat, tin, tout, errors, pending = {}, [], 0, 0, 0, 0
    for c in suite["cases"]:
        a = answers.get(c["id"])
        if not a:
            pending += 1
            continue
        if a["error"]:
            errors += 1
            continue
        for f in fields:
            per_field[f][a["scores"].get(f, "missed")] += 1
        case_ok[c["id"]] = all(a["scores"].get(f) == "correct" for f in fields)
        lat.append(a["latency_ms"]); tin += a["tokens_in"] or 0; tout += a["tokens_out"] or 0
    scored = len(case_ok)
    total_fields = sum(sum(v.values()) for v in per_field.values())
    halluc = sum(v["hallucinated"] for v in per_field.values())
    null_expected = sum(1 for c in suite["cases"] for f in fields if c["expected"].get(f) is None and c["id"] in case_ok)
    lat.sort()
    return {
        "run": run, "scored": scored, "errors": errors, "pending": pending,
        "case_accuracy": sum(case_ok.values()) / scored if scored else 0.0,
        "field_accuracy": sum(v["correct"] for v in per_field.values()) / total_fields if total_fields else 0.0,
        "hallucination_rate": halluc / null_expected if null_expected else 0.0,
        "per_field": {f: dict(per_field[f]) for f in fields},
        "case_ok": case_ok,
        "latency_p50": lat[len(lat) // 2] if lat else None,
        "latency_p90": lat[int(len(lat) * 0.9) - 1] if lat else None,
        "tokens_in": tin, "tokens_out": tout,
    }


def compare(a: dict, b: dict) -> dict:
    """b against a, on the cases both runs scored."""
    common = sorted(set(a["case_ok"]) & set(b["case_ok"]))
    x = [a["case_ok"][c] for c in common]
    y = [b["case_ok"][c] for c in common]
    if not common:
        return {"cases": 0}
    diff, low, high = paired_bootstrap(x, y)
    only_a, only_b, p = mcnemar_exact(x, y)
    return {"cases": len(common), "diff": diff, "low": low, "high": high, "only_a": only_a, "only_b": only_b,
            "p": p, "verdict": verdict(diff, low, high, p),
            "regressions": [c for c in common if a["case_ok"][c] and not b["case_ok"][c]],
            "fixes": [c for c in common if b["case_ok"][c] and not a["case_ok"][c]]}
