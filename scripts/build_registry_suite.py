"""Build the 'registry-extraction' suite from ClinicalTrials.gov.

Each case gives a model the free text of one trial (summary, description,
eligibility) and asks for facts the registry also stores as structured fields.
The structured fields are the answer key, with one rule that keeps the suite
fair and makes it measure hallucination: if a value is not stated in the text
the model sees, the expected answer is null ("not stated"), whatever the
registry says.

    python scripts/build_registry_suite.py --n 30 > suites/registry-extraction.json
"""

import argparse
import json
import random
import re
import sys
import urllib.parse
import urllib.request

API = "https://clinicaltrials.gov/api/v2/studies"
CONDITIONS = ["lung cancer", "breast cancer", "colorectal cancer", "melanoma", "lymphoma", "prostate cancer"]
MAX_CHARS = 4500


def fetch(condition: str, n: int) -> list[dict]:
    q = urllib.parse.urlencode({"query.cond": condition, "filter.overallStatus": "RECRUITING", "pageSize": n})
    req = urllib.request.Request(f"{API}?{q}", headers={"user-agent": "eval-lab/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("studies", [])


def words_number(n: int) -> list[str]:
    return [str(n), f"{n:,}", f"{n:,}".replace(",", "'"), f"{n:,}".replace(",", " ")]


def stated_number(n: int | None, text: str) -> bool:
    if n is None:
        return False
    return any(re.search(rf"(?<![\d.,']){re.escape(w)}(?![\d])", text) for w in words_number(n))


def phase_label(phases: list[str]) -> str | None:
    if not phases or phases == ["NA"]:
        return None
    nums = sorted({p.replace("EARLY_PHASE1", "0").replace("PHASE", "") for p in phases})
    return "/".join(nums)


def phase_stated(label: str | None, text: str) -> bool:
    if label is None:
        return False
    t = text.lower()
    roman = {"0": "0", "1": "i", "2": "ii", "3": "iii", "4": "iv"}
    for part in label.split("/"):
        # "Phase 2", "phase II", "Phase 2b", "Phase Ib" all state the phase.
        if not re.search(rf"phase\s*(?:{part}|{roman[part]})(?:[ab]\b|\b)", t):
            return False
    return True


def case(study: dict) -> dict | None:
    p = study["protocolSection"]
    desc, elig, design = p.get("descriptionModule", {}), p.get("eligibilityModule", {}), p.get("designModule", {})
    text = "\n\n".join(x for x in [
        "Summary: " + desc.get("briefSummary", ""),
        "Description: " + desc.get("detailedDescription", ""),
        "Eligibility: " + elig.get("eligibilityCriteria", ""),
    ] if len(x) > 14)
    if len(text) < 600:
        return None
    text = text[:MAX_CHARS]
    enrollment = (design.get("enrollmentInfo") or {}).get("count")
    min_age_raw = elig.get("minimumAge", "")
    min_age = int(min_age_raw.split()[0]) if min_age_raw.endswith("Years") else None
    phase = phase_label(design.get("phases") or [])
    expected = {
        "study_type": design.get("studyType", "").lower() or None,
        "phase": phase if phase_stated(phase, text) else None,
        "enrollment": enrollment if stated_number(enrollment, text) else None,
        "minimum_age": min_age if min_age is not None and stated_number(min_age, text.split("Eligibility:")[-1]) else None,
    }
    return {"id": p["identificationModule"]["nctId"], "input": {"text": text}, "expected": expected,
            "source": f"https://clinicaltrials.gov/study/{p['identificationModule']['nctId']}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    pool = []
    for c in CONDITIONS:
        pool += [x for x in (case(s) for s in fetch(c, 40)) if x]
    random.Random(args.seed).shuffle(pool)
    seen, cases = set(), []
    for c in pool:
        if c["id"] not in seen:
            seen.add(c["id"]); cases.append(c)
        if len(cases) == args.n:
            break
    suite = {
        "name": "registry-extraction",
        "description": "Recover structured trial facts from free text. Expected values come from the registry's "
                       "structured fields; a value not stated in the text must be answered as null.",
        "fields": {
            "study_type": {"scorer": "exact", "values": ["interventional", "observational"]},
            "phase": {"scorer": "exact"},
            "enrollment": {"scorer": "number"},
            "minimum_age": {"scorer": "number"},
        },
        "prompts": {
            "v1": {"system": "Extract facts about a clinical trial from its text. Reply with JSON only: "
                             '{"study_type": "interventional" or "observational", "phase": e.g. "2" or "1/2", '
                             '"enrollment": number of participants, "minimum_age": minimum age in years}',
                   "user": "{text}"},
            "v2": {"system": "Extract facts about a clinical trial from its text. Use only what the text states. "
                             "If the text does not state a value, answer null; never estimate or use outside knowledge. "
                             'Reply with JSON only: {"study_type": "interventional" or "observational", '
                             '"phase": e.g. "2" or "1/2" or null, "enrollment": planned number of participants or null, '
                             '"minimum_age": minimum age in years or null}',
                   "user": "{text}"},
        },
        "cases": cases,
    }
    json.dump(suite, sys.stdout, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
