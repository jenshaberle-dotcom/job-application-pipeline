"""Optional research adapter for dreamjobs-tech/skill-extractor.

This file is intentionally outside the JAP runtime dependency graph. It expects
``skill-extractor==0.2.0`` to be installed only in the research environment and
uses its bundled gazetteer as a recall sensor. No MiniLM model is loaded and no
external classification result becomes JAP truth.

Input (stdin):  {"schema": "jap.external_evidence_observer.v1", "text": "..."}
Output (stdout): one JSON object containing exact skill span proposals.
"""

from __future__ import annotations

from importlib import resources
import json
import sys


def main() -> int:
    try:
        from skill_extractor.matcher import KeywordMatcher
    except ImportError as exc:
        print(f"skill-extractor is not installed: {exc}", file=sys.stderr)
        return 2

    try:
        request = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(f"invalid request JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(request, dict):
        print("request must be a JSON object", file=sys.stderr)
        return 2
    text = str(request.get("text") or "")

    data = resources.files("skill_extractor") / "data" / "skills.json"
    with data.open(encoding="utf-8") as handle:
        matcher = KeywordMatcher(json.load(handle))

    observations: list[dict[str, object]] = []
    for canonical_skill, start, end in matcher.extract(text):
        if start < 0 or end <= start or end > len(text):
            continue
        evidence = text[start:end]
        if not evidence:
            continue
        observations.append(
            {
                "field": "skills",
                "value": canonical_skill,
                "evidence": evidence,
                "start": start,
                "end": end,
                "basis": "dreamjobs_skill_extractor_gazetteer",
            }
        )

    print(
        json.dumps(
            {
                "schema": "jap.external_evidence_observer.v1",
                "observer": "dreamjobs_skill_extractor_gazetteer_0.2.0",
                "observations": observations,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
