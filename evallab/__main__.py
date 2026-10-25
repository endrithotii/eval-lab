"""Command line.

  python -m evallab run     --suite suites/registry-extraction.json --model groq:qwen/qwen3.8-27b --prompt v2
  python -m evallab report  --suite suites/registry-extraction.json --out site/index.html
  python -m evallab gate    --suite suites/registry-extraction.json --baseline 1 --candidate 2 --max-drop 0.05
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import compare, summarise
from .llm import make_model
from .report import page
from .runner import rescore, run
from .store import Store


def load_suite(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def summaries(store: Store, suite: dict) -> list[dict]:
    return [summarise(store, suite, r) for r in store.runs(suite["name"])]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="evallab")
    ap.add_argument("--db", type=Path, default=Path("runs.db"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one model and prompt version over a suite (resumable)")
    r.add_argument("--suite", type=Path, required=True)
    r.add_argument("--model", required=True, help="provider:model, e.g. groq:qwen/qwen3.8-27b")
    r.add_argument("--prompt", required=True, help="a prompt version defined in the suite, e.g. v2")
    r.add_argument("--note", default="")

    rs = sub.add_parser("rescore", help="apply the current answer key and scorers to stored answers (no model calls)")
    rs.add_argument("--suite", type=Path, required=True)

    s = sub.add_parser("list", help="list runs with their headline numbers")
    s.add_argument("--suite", type=Path, required=True)

    rep = sub.add_parser("report", help="write the HTML dashboard")
    rep.add_argument("--suite", type=Path, required=True)
    rep.add_argument("--out", type=Path, default=Path("site/index.html"))
    rep.add_argument("--baseline", type=int, default=1, help="run number to compare the others against")

    g = sub.add_parser("gate", help="exit 1 if the candidate is clearly worse than the baseline (for CI)")
    g.add_argument("--suite", type=Path, required=True)
    g.add_argument("--baseline", type=int, required=True)
    g.add_argument("--candidate", type=int, required=True)
    g.add_argument("--max-drop", type=float, default=0.0, help="allowed drop in cases fully correct")
    g.add_argument("--max-hallucination", type=float, default=1.0)

    args = ap.parse_args(argv)
    store = Store(args.db)
    suite = load_suite(args.suite)

    if args.cmd == "run":
        try:
            model = make_model(args.model)
        except (RuntimeError, ValueError) as e:
            print(f"Cannot start: {e}", file=sys.stderr)
            return 2
        res = run(suite, model, args.prompt, store, args.note)
        print(json.dumps(res))
        return 0 if res["complete"] else 3

    if args.cmd == "rescore":
        print(f"{rescore(suite, store)} answers rescored")
        return 0

    ss = summaries(store, suite)
    if args.cmd == "list":
        for i, s in enumerate(ss, start=1):
            print(f"{i}. {s['run']['model']} {s['run']['prompt']}: cases {s['case_accuracy']:.0%}, "
                  f"fields {s['field_accuracy']:.0%}, hallucination {s['hallucination_rate']:.0%}, "
                  f"{s['scored']} scored{'' if s['run']['complete'] else ', incomplete'}")
        return 0
    if args.cmd == "report":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(page(suite, ss, baseline=args.baseline - 1), encoding="utf-8")
        print(args.out)
        return 0
    if args.cmd == "gate":
        a, b = ss[args.baseline - 1], ss[args.candidate - 1]
        c = compare(a, b)
        drop = -c["diff"]
        ok = not (c["verdict"] == "worse" and drop > args.max_drop) and b["hallucination_rate"] <= args.max_hallucination
        print(f"candidate {b['run']['model']} {b['run']['prompt']}: {c['diff']:+.1%} "
              f"(95% {c['low']:+.1%} to {c['high']:+.1%}, p={c['p']:.3f}), "
              f"hallucination {b['hallucination_rate']:.0%}: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
