"""Comparing two runs on the same cases, without fooling ourselves.

Two variants are compared case by case (paired), because the same hard case is
hard for both. Two tools:

- a paired bootstrap confidence interval for the difference in accuracy;
- an exact McNemar test on the cases where exactly one variant was right.

With 30 cases, a few points of difference is often noise. These numbers say so.
"""

from __future__ import annotations

import math
import random


def accuracy(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def paired_bootstrap(a: list[bool], b: list[bool], reps: int = 5000, seed: int = 13) -> tuple[float, float, float]:
    """Difference b - a in accuracy, with a 95% interval from resampling cases."""
    assert len(a) == len(b) and a, "runs must cover the same cases"
    n, rng = len(a), random.Random(seed)
    diffs = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(b[i] for i in idx) / n - sum(a[i] for i in idx) / n)
    diffs.sort()
    return accuracy(b) - accuracy(a), diffs[int(0.025 * reps)], diffs[int(0.975 * reps) - 1]


def mcnemar_exact(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """Cases only a got right, cases only b got right, and the two-sided exact p-value."""
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    n = only_a + only_b
    if n == 0:
        return only_a, only_b, 1.0
    k = min(only_a, only_b)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return only_a, only_b, min(1.0, 2 * p)


def verdict(diff: float, low: float, high: float, p: float) -> str:
    if low > 0 and p < 0.05:
        return "better"
    if high < 0 and p < 0.05:
        return "worse"
    return "no clear difference"
