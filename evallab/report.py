"""One static HTML page for a suite: the verdicts first, then every run on one scoreboard."""

from __future__ import annotations

from html import escape

from .analysis import OUTCOMES, compare


def _e(x) -> str:
    return escape("" if x is None else str(x))


def pct(x: float) -> str:
    return f"{round(100 * x)}%"


LABEL = {"correct": "correct", "wrong": "wrong value", "missed": "missed, although stated",
         "hallucinated": "invented, although not stated"}


def _fields(per_field: dict) -> str:
    rows = ""
    for f, c in per_field.items():
        n = sum(c.values()) or 1
        segs = "".join(f'<span class="seg {o}" style="flex:{c.get(o, 0)}" title="{LABEL[o]}: {c.get(o, 0)}"></span>'
                       for o in OUTCOMES if c.get(o))
        rows += (f'<div class="field"><span class="fname">{_e(f.replace("_", " "))}</span>'
                 f'<span class="track">{segs}</span><span class="fnum">{c.get("correct", 0)}/{n}</span></div>')
    return rows


def _scatter(summaries: list[dict]) -> str:
    """Accuracy against hallucination rate: up and to the left is better."""
    w, h, pad = 580, 340, 64
    x = lambda v: pad + v * (w - 2 * pad)
    y = lambda v: h - pad - v * (h - 2 * pad)
    grid = "".join(f'<line x1="{pad}" x2="{w - pad}" y1="{y(t):.1f}" y2="{y(t):.1f}" class="grid"/>'
                   f'<text x="{pad - 10}" y="{y(t) + 4:.1f}" class="tick" text-anchor="end">{int(t * 100)}%</text>'
                   for t in (0, 0.25, 0.5, 0.75, 1))
    xt = "".join(f'<text x="{x(t):.1f}" y="{h - pad + 20}" class="tick" text-anchor="middle">{int(t * 100)}%</text>'
                 for t in (0, 0.25, 0.5, 0.75, 1))
    # The good corner is shaded so the eye knows where to look.
    zone = f'<rect x="{pad}" y="{pad}" width="{(w - 2 * pad) * 0.25:.1f}" height="{(h - 2 * pad) * 0.25:.1f}" class="zone"/>'
    pts = ""
    for i, s in enumerate(summaries, start=1):
        cx, cy = x(s["hallucination_rate"]), y(s["case_accuracy"])
        pts += (f'<g class="pt"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="15"/>'
                f'<text x="{cx:.1f}" y="{cy + 5:.1f}" text-anchor="middle">{i}</text>'
                f'<title>Run {i}: {_e(s["run"]["model"])}, prompt {_e(s["run"]["prompt"])}</title></g>')
    return (f'<svg viewBox="0 0 {w} {h}" class="scatter" role="img" aria-label="Cases fully correct against hallucination rate, one circle per run">'
            f'{zone}<text x="{pad + 8}" y="{pad + 18}" class="zlabel">the good corner</text>{grid}{xt}'
            f'<text x="{w / 2}" y="{h - 8}" class="axis" text-anchor="middle">hallucination rate, lower is better</text>'
            f'<text x="18" y="{h / 2}" class="axis" transform="rotate(-90 18 {h / 2})" text-anchor="middle">cases fully correct</text>'
            f'{pts}</svg>')


def _verdicts(summaries: list[dict], baseline: int) -> str:
    base = summaries[baseline] if summaries else None
    tiles = ""
    for i, s in enumerate(summaries, start=1):
        if s is base:
            continue
        c = compare(base, s)
        if not c.get("cases"):
            continue
        v = c["verdict"]
        word = {"better": "Better", "worse": "Worse"}.get(v, "No clear difference")
        cls = {"better": "better", "worse": "worse"}.get(v, "unclear")
        reg = c["regressions"]
        tiles += f"""
<article class="verdict {cls}">
  <p class="pair"><span class="chip">{i}</span> against <span class="chip">{baseline + 1}</span></p>
  <p class="word">{word}</p>
  <p class="diff">{c['diff'] * 100:+.0f} points of cases fully correct</p>
  <p class="detail">95% interval {c['low'] * 100:+.0f} to {c['high'] * 100:+.0f} points. Exact McNemar test on the {c['only_a'] + c['only_b']} cases where only one run was right: p = {c['p']:.3f}.
  {f"Got worse on {len(reg)} case{'s' if len(reg) != 1 else ''}: {_e(', '.join(reg[:4]))}{' …' if len(reg) > 4 else ''}." if reg else "No case got worse."}</p>
</article>"""
    return tiles


def page(suite: dict, summaries: list[dict], baseline: int = 0) -> str:
    board = ""
    for i, s in enumerate(summaries, start=1):
        r = s["run"]
        hall = s["hallucination_rate"]
        status = []
        if s["errors"]:
            status.append(f'{s["errors"]} failed')
        if s["pending"]:
            status.append(f'{s["pending"]} not run yet')
        board += f"""
<tr>
  <th scope="row"><span class="chip">{i}</span></th>
  <td class="who"><b>{_e(r['model'])}</b><span>prompt {_e(r['prompt'])}, {s['scored']} cases scored{(", " + ", ".join(status)) if status else ""}</span></td>
  <td class="big"><span class="n">{pct(s['case_accuracy'])}</span><span class="meter"><span style="width:{100 * s['case_accuracy']:.0f}%"></span></span></td>
  <td class="big {'alarm' if hall > 0.1 else ''}"><span class="n">{pct(hall)}</span><span class="meter pink"><span style="width:{100 * hall:.0f}%"></span></span></td>
  <td class="fields">{_fields(s['per_field'])}</td>
  <td class="small">{_e(s['latency_p50'])} ms<br>{s['tokens_in']:,} in, {s['tokens_out']:,} out</td>
</tr>"""

    verdicts = _verdicts(summaries, baseline)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>{_e(suite['name'])}: eval-lab</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&display=swap">
<style>{CSS}</style></head><body>
<header class="wrap top">
  <p class="name">eval-lab, suite {_e(suite['name'])}</p>
  <h1>Did the change make the model better, or does it only look that way?</h1>
  <p class="lede">{_e(suite['description'])} {len(suite['cases'])} cases; fields {_e(', '.join(suite['fields']))}.</p>
</header>
<main>
  <section class="wrap" aria-label="Verdicts">
    <div class="verdicts">{verdicts or '<p>Run at least two variants to compare.</p>'}</div>
    <p class="rule">A verdict says <em>better</em> or <em>worse</em> only when the paired bootstrap interval and the exact McNemar test agree. Otherwise it says no clear difference, even if one number is higher.</p>
  </section>
  <section class="wrap" aria-labelledby="board-h">
    <h2 id="board-h">Every run</h2>
    <div class="board-wrap"><table class="board">
      <thead><tr><th scope="col">Run</th><th scope="col">Model and prompt</th><th scope="col">Cases fully correct</th><th scope="col">Hallucination rate</th><th scope="col">Each field</th><th scope="col">Median latency, tokens</th></tr></thead>
      <tbody>{board}</tbody></table></div>
    <ul class="legend">
      <li><span class="seg correct"></span>{LABEL['correct']}</li><li><span class="seg wrong"></span>{LABEL['wrong']}</li>
      <li><span class="seg missed"></span>{LABEL['missed']}</li><li><span class="seg hallucinated"></span>{LABEL['hallucinated']}</li>
    </ul>
  </section>
  <section class="wrap split" aria-labelledby="map-h">
    <div><h2 id="map-h">Where each run lands</h2>{_scatter(summaries)}</div>
    <div class="explain">
      <h3>Why hallucination is counted on its own</h3>
      <p>A model that misreads a number and a model that invents one are different risks. A value counts as stated only if it appears in the text the model saw; otherwise the right answer is null, and any value is counted as invented.</p>
      <p>The hallucination rate is the invented answers divided by the fields whose right answer is null.</p>
    </div>
  </section>
</main>
<footer class="wrap foot"><p>Answer key: ClinicalTrials.gov structured fields. Every answer, score, latency and token count is stored in runs.db.</p></footer>
</body></html>"""


# Deep navy keeps attention on the numbers and is easy on the eyes for long
# analysis. Saffron marks the verdicts, the thing to read first. Teal and
# orange separate right from wrong; hot pink is reserved for invented values,
# so the most dangerous failure never blends in with an ordinary mistake.
CSS = """
:root { --night: #131B3A; --deck: #1B2550; --deck2: #222D60; --line: #34417A; --text: #F5F1E6; --soft: #AEB7DA;
  --saffron: #FFC233; --correct: #3DD6C1; --wrong: #FF8A3D; --missed: #7C87B3; --hallucinated: #FF4F9A;
  --font: "Archivo", "Arial Narrow", Arial, sans-serif; }
* { box-sizing: border-box; }
html { background: var(--night); color: var(--text); }
body { margin: 0; font: 400 17px/1.55 var(--font); font-stretch: 100%; }
a { color: var(--saffron); }
:focus-visible { outline: 3px solid var(--saffron); outline-offset: 3px; }
.wrap { max-width: 80rem; margin-inline: auto; padding-inline: 1.25rem; }
.top { padding-block: 3rem 1.6rem; }
.name { margin: 0 0 0.8rem; color: var(--saffron); font-weight: 600; font-stretch: 80%; font-size: 1.05rem; }
h1 { font-weight: 800; font-stretch: 125%; font-size: clamp(1.9rem, 4.4vw, 3.3rem); line-height: 1.05; margin: 0; max-width: 24ch; letter-spacing: -0.01em; }
h2 { font-weight: 800; font-stretch: 112%; font-size: 1.5rem; margin: 0 0 1rem; }
h3 { font-weight: 700; font-stretch: 100%; font-size: 1.1rem; margin: 0 0 0.6rem; color: var(--saffron); }
.lede { max-width: 66ch; color: var(--soft); margin: 1.1rem 0 0; }
section { margin-top: 2.6rem; }

.verdicts { display: grid; grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr)); gap: 1.2rem; }
.verdict { background: var(--deck); padding: 1.4rem 1.5rem 1.5rem; border-left: 0.7rem solid var(--missed); }
.verdict.better { border-left-color: var(--correct); } .verdict.worse { border-left-color: var(--hallucinated); }
.pair { margin: 0; color: var(--soft); display: flex; align-items: center; gap: 0.5rem; }
.chip { display: inline-grid; place-items: center; min-width: 2rem; height: 2rem; padding-inline: 0.4rem; background: var(--saffron); color: var(--night); font-weight: 800; font-stretch: 112%; border-radius: 0.35rem; }
.word { font-weight: 800; font-stretch: 125%; font-size: clamp(2.2rem, 5vw, 3.6rem); line-height: 1; margin: 0.6rem 0 0.4rem; }
.verdict.better .word { color: var(--correct); } .verdict.worse .word { color: var(--hallucinated); } .verdict.unclear .word { color: var(--text); font-size: clamp(1.7rem, 3.6vw, 2.5rem); }
.diff { font-weight: 700; font-size: 1.15rem; margin: 0 0 0.5rem; }
.detail { color: var(--soft); margin: 0; font-size: 0.95rem; }
.rule { color: var(--soft); max-width: 70ch; margin: 1rem 0 0; font-size: 0.95rem; }
.rule em { color: var(--saffron); font-style: normal; font-weight: 700; }

.board-wrap { overflow-x: auto; }
.board { border-collapse: separate; border-spacing: 0 0.5rem; width: 100%; min-width: 58rem; }
.board th, .board td { text-align: left; vertical-align: middle; padding: 0.9rem 1rem; }
.board thead th { color: var(--soft); font-weight: 600; font-stretch: 80%; font-size: 0.95rem; padding-block: 0 0.2rem; }
.board tbody tr { background: var(--deck); }
.board tbody tr:nth-child(even) { background: var(--deck2); }
.who b { display: block; font-weight: 700; }
.who span, .small { color: var(--soft); font-size: 0.88rem; }
.big .n { display: block; font-weight: 800; font-stretch: 125%; font-size: 2.1rem; line-height: 1; }
.big.alarm .n { color: var(--hallucinated); }
.meter { display: block; height: 0.45rem; width: 7.5rem; background: var(--line); margin-top: 0.5rem; }
.meter span { display: block; height: 100%; background: var(--correct); }
.meter.pink span { background: var(--hallucinated); }
.fields { min-width: 17rem; }
.field { display: grid; grid-template-columns: 6.5rem 1fr 2.6rem; gap: 0.6rem; align-items: center; font-size: 0.88rem; margin: 0.2rem 0; }
.fname { font-stretch: 80%; color: var(--soft); }
.track { display: flex; height: 0.75rem; background: var(--line); }
.fnum { text-align: right; font-stretch: 80%; }
.seg { display: inline-block; height: 100%; }
.seg.correct { background: var(--correct); } .seg.wrong { background: var(--wrong); }
.seg.missed { background: var(--missed); } .seg.hallucinated { background: var(--hallucinated); }
.legend { list-style: none; display: flex; flex-wrap: wrap; gap: 0.6rem 1.6rem; padding: 0; margin: 0.6rem 0 0; color: var(--soft); font-size: 0.92rem; }
.legend li { display: flex; align-items: center; gap: 0.5rem; }
.legend .seg { width: 1.1rem; height: 1.1rem; }

.split { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 2.4rem; align-items: start; }
.scatter { width: 100%; max-width: 600px; height: auto; display: block; background: var(--deck); }
.scatter .grid { stroke: var(--line); } .scatter .tick, .scatter .axis { fill: var(--soft); font: 13px var(--font); }
.scatter .zone { fill: var(--correct); fill-opacity: 0.12; } .scatter .zlabel { fill: var(--correct); font: 600 13px var(--font); }
.scatter .pt circle { fill: var(--saffron); } .scatter .pt text { fill: var(--night); font: 800 14px var(--font); }
.explain { background: var(--deck); padding: 1.4rem 1.5rem; }
.explain p { margin: 0 0 0.8rem; color: var(--soft); }
.foot { color: var(--soft); font-size: 0.88rem; padding-block: 2.6rem 3rem; }
@media (max-width: 860px) { .split { grid-template-columns: 1fr; } }
@media (max-width: 700px) {
  .board { min-width: 0; border-spacing: 0; }
  .board thead { display: none; }
  .board, .board tbody, .board tr, .board th, .board td { display: block; }
  .board tbody tr { margin-bottom: 0.8rem; padding: 0.4rem 0; }
  .board th, .board td { padding: 0.45rem 1rem; }
  .board td.big { display: inline-block; width: 49%; vertical-align: top; }
  .board td.big::before { display: block; color: var(--soft); font-size: 0.85rem; margin-bottom: 0.3rem; }
  .board td.big:nth-of-type(2)::before { content: "Cases fully correct"; }
  .board td.big:nth-of-type(3)::before { content: "Hallucination rate"; }
  .meter { width: 90%; }
  .fields { min-width: 0; }
}
"""
