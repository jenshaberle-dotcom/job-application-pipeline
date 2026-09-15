"""Research-only learned context filter for dreamjobs-tech/skill-extractor.

Unlike the gazetteer-only observer, this adapter runs the package's quantized
MiniLM + MLP context classifier. It remains an optional Shadow comparator:
classifier decisions and canonical names have zero JAP authority. Accepted
outputs are still exact spans from the bounded employer-origin requirement text
and must pass the tool-neutral JAP verifier.

The classifier is English-trained, so multilingual results are diagnostic only.
"""

from __future__ import annotations

import json
import os
import sys


DEFAULT_THRESHOLD = 0.5


def _threshold() -> float:
    raw = os.environ.get("DREAMJOBS_SKILL_THRESHOLD", str(DEFAULT_THRESHOLD))
    value = float(raw)
    if not 0.0 <= value <= 1.0:
        raise ValueError("DREAMJOBS_SKILL_THRESHOLD must be between 0 and 1")
    return value


def main() -> int:
    try:
        from skill_extractor import SkillExtractor
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

    try:
        threshold = _threshold()
        extractor = SkillExtractor(quantized=True)
        matches = extractor.matcher.extract(text)
        candidates = extractor.candidates(text)
        if len(matches) != len(candidates):
            raise RuntimeError("classifier candidate/matcher cardinality mismatch")
        if not matches:
            probabilities: list[float] = []
        else:
            inputs: list[str] = []
            for (skill, _start, _end), (candidate_skill, context) in zip(
                matches, candidates, strict=True
            ):
                if skill != candidate_skill:
                    raise RuntimeError("classifier candidate/matcher order mismatch")
                inputs.append(f"{skill} : {context}")
            probabilities = [
                float(value)
                for value in extractor.mlp.predict_proba(extractor.embedder.encode(inputs))
            ]
    except Exception as exc:
        print(f"skill classifier failed: {exc}", file=sys.stderr)
        return 2

    observations: list[dict[str, object]] = []
    for (canonical_skill, start, end), probability in zip(
        matches, probabilities, strict=True
    ):
        if probability < threshold:
            continue
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
                "confidence": probability,
                "basis": "dreamjobs_skill_extractor_context_classifier",
            }
        )

    print(
        json.dumps(
            {
                "schema": "jap.external_evidence_observer.v1",
                "observer": "dreamjobs_skill_extractor_classifier_0.2.0",
                "observations": observations,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
