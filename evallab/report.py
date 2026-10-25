"""One static HTML dashboard for a suite: every run, side by side, and what changed."""

from __future__ import annotations

from html import escape

from .analysis import OUTCOMES, compare


def _e(x) -> str:
    return escape("" if x is None else str(x))


def pct(x: float) -> str:
    return f"{round(100 * x)}%"


def _bars(per_field: dict) -> str:
    rows = ""
    for f, c in per_field.items():
        n = sum(c.values()) or 1
        segs = "".join(f'<span class="seg {o}" style="width:{100 * c.get(o, 0) / n:.1f}%" title="{o}: {c.get(o, 0)}"></span>'
                       for o in OUTCOMES if c.get(o))
        rows += (f'<div class="fbar"><span class="fname">{_e(f.replace("_", " "))}</span>'
                 f'<span class="track">{segs}</span><span class="fnum">{c.get("correct", 0)}/{n}</span></div>')
    return rows


def _scatter(summaries: list[dict]) -> str:
    """Accuracy against hallucination rate: up and to the left is better."""
    w, h, pad = 520, 300, 46
    pts, labels = "", ""
    for i, s in enumerate(summaries):
        x = pad + s["hallucination_rate"] * (w - 2 * pad)
        y = h - pad - s["case_accuracy"] * (h - 2 * pad)
        pts += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" class="pt"><title>{_e(s["run"]["model"])} {_e(s["run"]["prompt"])}</title></circle>'
        labels += f'<text x="{x + 11:.1f}" y="{y + 4:.1f}" class="lbl">{i + 1}</text>'
    grid = "".join(f'<line x1="{pad}" x2="{w - pad}" y1="{h - pad - t * (h - 2 * pad):.1f}" y2="{h - pad - t * (h - 2 * pad):.1f}" class="grid"/>'
                   f'<text x="{pad - 8}" y="{h - pad - t * (h - 2 * pad) + 4:.1f}" class="tick" text-anchor="end">{int(t * 100)}%</text>'
                   for t in (0, 0.25, 0.5, 0.75, 1))
    xt = "".join(f'<text x="{pad + t * (w - 2 * pad):.1f}" y="{h - pad + 18}" class="tick" text-anchor="middle">{int(t * 100)}%</text>'
                 for t in (0, 0.25, 0.5, 0.75, 1))
    return (f'<svg viewBox="0 0 {w} {h}" class="scatter" role="img" aria-label="Accuracy against hallucination rate per run">'
            f'{grid}{xt}<text x="{w / 2}" y="{h - 6}" class="axis" text-anchor="middle">hallucination rate (lower is better)</text>'
            f'<text x="12" y="{h / 2}" class="axis" transform="rotate(-90 12 {h / 2})" text-anchor="middle">cases fully correct</text>'
            f'{pts}{labels}</svg>')


def page(suite: dict, summaries: list[dict], baseline: int = 0) -> str:
    cards = ""
    for i, s in enumerate(summaries, start=1):
        r = s["run"]
        cards += f"""
<article class="run">
  <header><span class="num">{i}</span><div><h3>{_e(r['model'])}</h3><p class="meta">prompt {_e(r['prompt'])} · {_e(r['prompt_hash'])} · {_e((r['finished'] or r['started'])[:16].replace('T', ' '))}{'' if r['complete'] else ' · incomplete'}</p></div></header>
  <dl class="kpis">
    <div><dt>Cases fully correct</dt><dd>{pct(s['case_accuracy'])}</dd></div>
    <div><dt>Fields correct</dt><dd>{pct(s['field_accuracy'])}</dd></div>
    <div class="{'bad' if s['hallucination_rate'] > 0.1 else ''}"><dt>Hallucination rate</dt><dd>{pct(s['hallucination_rate'])}</dd></div>
    <div><dt>Median latency</dt><dd>{_e(s['latency_p50'])} ms</dd></div>
  </dl>
  <div class="bars">{_bars(s['per_field'])}</div>
  <p class="meta">{s['scored']} cases scored{f", {s['errors']} failed" if s['errors'] else ""}{f", {s['pending']} not run yet" if s['pending'] else ""} · {s['tokens_in']:,} tokens in, {s['tokens_out']:,} out</p>
</article>"""

    comps = ""
    base = summaries[baseline] if summaries else None
    for i, s in enumerate(summaries, start=1):
        if s is base:
            continue
        c = compare(base, s)
        if not c.get("cases"):
            continue
        comps += (f'<tr><td>{i} against {baseline + 1}</td><td class="num">{c["diff"]:+.0%}</td>'
                  f'<td class="num">{c["low"]:+.0%} to {c["high"]:+.0%}</td><td class="num">{c["only_a"]} / {c["only_b"]}</td>'
                  f'<td class="num">{c["p"]:.3f}</td><td class="v {c["verdict"].split()[0]}">{_e(c["verdict"])}</td>'
                  f'<td>{_e(", ".join(c["regressions"][:4]))}{" …" if len(c["regressions"]) > 4 else ""}</td></tr>')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>{_e(suite['name'])}: eval-lab</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&family=Fira+Code:wght@400;500&display=swap">
<style>{CSS}</style></head><body>
<header class="wrap top">
  <p class="crumb">eval-lab</p>
  <h1>{_e(suite['name'])}</h1>
  <p class="lede">{_e(suite['description'])}</p>
  <p class="meta">{len(suite['cases'])} cases · fields: {_e(', '.join(suite['fields']))}</p>
</header>
<main class="wrap">
  <section class="overview">
    <div><h2>Accuracy against hallucination</h2><p class="meta">Each dot is a run. Up and to the left is better.</p>{_scatter(summaries)}</div>
    <div class="legend"><h2>Field outcomes</h2>
      <p><span class="seg correct"></span> correct</p><p><span class="seg wrong"></span> wrong value</p>
      <p><span class="seg missed"></span> missed, although stated</p><p><span class="seg hallucinated"></span> invented, although not stated</p>
      <p class="meta">A value counts as stated only if it appears in the text the model saw. Otherwise the right answer is null.</p></div>
  </section>
  <section><h2>Runs</h2><div class="runs">{cards}</div></section>
  <section><h2>Is it really better?</h2>
    <p class="meta">Paired comparison on the same cases: bootstrap interval for the difference in cases fully correct, and an exact McNemar test on the cases where exactly one run was right.</p>
    <div class="table-wrap"><table><thead><tr><th>Comparison</th><th>Difference</th><th>95% interval</th><th>Only base / only new</th><th>p</th><th>Verdict</th><th>Regressed cases</th></tr></thead>
    <tbody>{comps or '<tr><td colspan="7">Run at least two variants to compare.</td></tr>'}</tbody></table></div>
  </section>
</main>
<footer class="wrap"><p>Answer key: ClinicalTrials.gov structured fields. Every answer is stored in runs.db.</p></footer>
</body></html>"""


CSS = """
:root { --bg: #F6F5FA; --card: #FFFFFF; --ink: #1B1A2E; --muted: #5E5C74; --rule: #DDDBE8; --accent: #5B3FD0;
  --correct: #2E8A6E; --wrong: #D08A1E; --missed: #A8A6BC; --hallucinated: #C8364D;
  --sans: "Manrope", "Segoe UI", system-ui, sans-serif; --mono: "Fira Code", ui-monospace, monospace; }
* { box-sizing: border-box; }
html { background: var(--bg); color: var(--ink); }
body { margin: 0; font: 16px/1.55 var(--sans); }
.wrap { max-width: 74rem; margin: 0 auto; padding-inline: 1.25rem; }
.top { padding-block: 2.5rem 1rem; }
.crumb { margin: 0; color: var(--accent); font: 500 0.9rem var(--mono); }
h1 { font: 700 clamp(1.9rem, 4vw, 2.7rem)/1.1 var(--sans); margin: 0.3rem 0 0; letter-spacing: -0.02em; }
h2 { font: 700 1.15rem var(--sans); margin: 0 0 0.5rem; }
h3 { font: 600 1rem var(--mono); margin: 0; }
.lede { max-width: 64ch; margin: 0.7rem 0 0.4rem; }
.meta { color: var(--muted); font-size: 0.88rem; margin: 0.2rem 0 0; }
section { margin: 2.2rem 0 0; }
.overview { display: grid; grid-template-columns: minmax(0, 1.4fr) 1fr; gap: 2rem; align-items: start; background: var(--card); border: 1px solid var(--rule); padding: 1.4rem; border-radius: 10px; }
.scatter { width: 100%; max-width: 560px; height: auto; display: block; margin-top: 0.5rem; }
.scatter .grid { stroke: var(--rule); } .scatter .tick, .scatter .axis { fill: var(--muted); font: 12px var(--sans); }
.scatter .pt { fill: var(--accent); fill-opacity: 0.85; } .scatter .lbl { fill: var(--ink); font: 600 13px var(--mono); }
.legend p { display: flex; align-items: center; gap: 0.5rem; margin: 0.3rem 0; }
.seg { display: inline-block; height: 100%; }
.legend .seg { width: 14px; height: 14px; border-radius: 3px; }
.seg.correct { background: var(--correct); } .seg.wrong { background: var(--wrong); }
.seg.missed { background: var(--missed); } .seg.hallucinated { background: var(--hallucinated); }
.runs { display: grid; grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr)); gap: 1rem; }
.run { background: var(--card); border: 1px solid var(--rule); border-radius: 10px; padding: 1.1rem 1.2rem; }
.run header { display: flex; gap: 0.8rem; align-items: flex-start; }
.num { font: 600 0.9rem var(--mono); color: var(--accent); }
.run .num { display: inline-grid; place-items: center; width: 1.8rem; height: 1.8rem; border-radius: 50%; background: #ECE8FB; flex: none; }
.kpis { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.6rem 1rem; margin: 1rem 0; }
.kpis dt { color: var(--muted); font-size: 0.8rem; } .kpis dd { margin: 0; font: 700 1.5rem var(--sans); }
.kpis .bad dd { color: var(--hallucinated); }
.fbar { display: grid; grid-template-columns: 7.5rem 1fr 3rem; gap: 0.6rem; align-items: center; font-size: 0.85rem; margin: 0.3rem 0; }
.track { display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: var(--rule); }
.fnum { font: 500 0.82rem var(--mono); color: var(--muted); text-align: right; }
.table-wrap { overflow-x: auto; background: var(--card); border: 1px solid var(--rule); border-radius: 10px; margin-top: 0.8rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
th, td { text-align: left; padding: 0.6rem 0.9rem; border-bottom: 1px solid var(--rule); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 0.82rem; }
td.num { font-family: var(--mono); white-space: nowrap; }
.v.better { color: var(--correct); font-weight: 700; } .v.worse { color: var(--hallucinated); font-weight: 700; }
.v.no { color: var(--muted); }
footer { color: var(--muted); font-size: 0.82rem; padding-block: 2rem 3rem; }
@media (max-width: 800px) { .overview { grid-template-columns: 1fr; } }
"""
