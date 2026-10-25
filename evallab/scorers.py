"""Field scorers. Each returns an outcome for one field of one case:

  correct       the expected value, or correctly null when nothing was stated
  wrong         a different value than the expected one
  missed        null, although the text states the value
  hallucinated  a value, although the text does not state one

Keeping "hallucinated" apart from "wrong" is the point: a model that invents
numbers is a different risk from one that misreads them.
"""

from __future__ import annotations

import re

NULLS = {"", "null", "none", "n/a", "na", "not stated", "not specified", "unknown", "not reported"}


def is_null(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower().strip(".") in NULLS)


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"\d[\d,' ]*(?:\.\d+)?", v)
        if m:
            return float(re.sub(r"[,' ]", "", m.group()))
    return None


def _norm(v) -> str:
    s = str(v).strip().lower()
    s = re.sub(r"^phase\s*", "", s)
    s = s.replace("phase", "").replace(" ", "")
    roman = {"iv": "4", "iii": "3", "ii": "2", "i": "1"}
    parts = re.split(r"[/,&]|and", s)
    out = []
    for p in parts:
        p = p.strip().rstrip("ab") if re.fullmatch(r"(?:\d|i{1,3}|iv)[ab]?", p.strip()) else p.strip()
        out.append(roman.get(p, p))
    return "/".join(sorted(x for x in out if x))


def exact(expected, got) -> str:
    return "correct" if _norm(expected) == _norm(got) else "wrong"


def number(expected, got, tol: float = 0.0) -> str:
    g = _num(got)
    if g is None:
        return "wrong"
    return "correct" if abs(g - float(expected)) <= tol else "wrong"


SCORERS = {"exact": exact, "number": number}


def score_field(spec: dict, expected, got) -> str:
    if spec.get("zero_is_null") and _num(got) == 0:
        got = None   # "0 participants" is a placeholder for "not known", not a claim
    if is_null(expected):
        return "correct" if is_null(got) else "hallucinated"
    if is_null(got):
        return "missed"
    return SCORERS[spec["scorer"]](expected, got)


def score_case(fields: dict, expected: dict, output: dict | None) -> dict[str, str]:
    output = output or {}
    return {f: score_field(spec, expected.get(f), output.get(f)) for f, spec in fields.items()}
