# eval-lab

Does the new prompt, or the new model, actually make the feature better? eval-lab answers with numbers you can defend: per-field outcomes, a hallucination rate, and a paired statistical comparison that refuses to call a winner when the difference is noise.

## What it measures

Every field of every answer gets one of four outcomes:

| Outcome | Meaning |
|---|---|
| correct | the expected value, or correctly `null` when the input does not state it |
| wrong | a different value |
| missed | `null`, although the input states the value |
| hallucinated | a value, although the input does not state one |

Keeping *hallucinated* apart from *wrong* is the point: a model that invents numbers is a different risk from one that misreads them. The **hallucination rate** is hallucinated answers divided by the fields whose correct answer is `null`.

Two runs are compared case by case on the same cases:

- a **paired bootstrap** 95% interval for the difference in cases fully correct;
- an **exact McNemar test** on the cases where exactly one run was right.

The verdict is *better* or *worse* only when both agree; otherwise *no clear difference*.

## The first suite: registry-extraction

30 real trials from ClinicalTrials.gov. The model reads a trial's free text (summary, description, eligibility) and returns study type, phase, planned enrolment and minimum age. The **answer key is the registry's own structured fields**, so no labels are invented, with one rule: if a value is not stated in the text the model sees, the expected answer is `null`. The suite builder checks this in code (`scripts/build_registry_suite.py`), so the suite measures hallucination directly: 20 of the 30 texts do not state the phase, 24 do not state the enrolment.

First results (Groq free tier, October 2026):

| Run | Model | Prompt | Cases fully correct | Hallucination rate |
|---|---|---|---|---|
| 1 | qwen3.8-27b | v1: "extract these fields" | 47% | 38% |
| 2 | qwen3.8-27b | v2: "only what the text states, otherwise null" | 80% | 6% |
| 3 | gpt-oss-20b | v2 | 81% (26 of 30 cases so far) | 2% |

Run 2 against run 1: +33 points (95% interval +17 to +50, McNemar p = 0.002): **better**. Run 3 against run 2: +4 points (interval −8 to +15, p = 1.0): **no clear difference**, despite the higher number.

Checking the first results by hand found two problems in the suite itself, both fixed with tests: "Phase 1/2a" was not recognised as stating the phase, and "0 participants" (a placeholder the v1 prompt forces) was counted as a hallucination. Fixing an answer key does not cost new model calls: `rescore` applies the current key and scorers to the stored answers.

## Use it

Python 3.10 or newer, standard library only.

```bash
export GROQ_API_KEY=...
python -m evallab run     --suite suites/registry-extraction.json --model groq:qwen/qwen3.8-27b --prompt v2
python -m evallab list    --suite suites/registry-extraction.json
python -m evallab report  --suite suites/registry-extraction.json --out site/index.html
python -m evallab gate    --suite suites/registry-extraction.json --baseline 2 --candidate 3 --max-drop 0.02
```

- Runs are **resumable**: a run is identified by the suite's inputs, the model and the prompt text, and only unanswered cases are sent. A run that reaches a provider's daily limit stops cleanly (exit code 3).
- `gate` exits with 1 when the candidate is clearly worse than the baseline or its hallucination rate is above `--max-hallucination`, for use in CI before a prompt or model change ships.
- Every answer, score, latency and token count is stored in `runs.db` (SQLite).
- Models: `groq:`, `gemini:`, `openai:`, `anthropic:` or `ollama:` followed by the model name.

## Write a suite

A suite is one JSON file: `fields` (each with a scorer: `exact` or `number`), `prompts` (named versions with a `system` and a `user` template), and `cases` (each with `input`, `expected` and a `source`). See `suites/registry-extraction.json`.

## Tests

```bash
python -m unittest discover -s tests
```

Includes a known McNemar value computed by hand, and the two suite bugs above.

## Limits

- 30 cases detect large differences, not small ones; the statistics say so rather than hide it.
- "Stated in the text" is decided by pattern matching, which can miss unusual phrasings. Disagreements are worth reading case by case in `runs.db`.
- Only exact and numeric scorers so far; free-text answers need a different scorer.
