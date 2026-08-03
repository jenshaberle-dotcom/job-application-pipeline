"""Pure structural similarity helpers for StepStone filter aliases.

The module intentionally compares parser-relevant string structure rather than
business or semantic company-name similarity. It performs no I/O and makes no
claim that a high similarity score proves a shared StepStone failure mechanism.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import quote


@dataclass(frozen=True)
class AliasFeatures:
    alias: str
    char_length: int
    utf8_bytes: int
    encoded_length: int
    word_count: int
    punctuation_count: int
    parenthesis_count: int
    ampersand_count: int
    digit_count: int
    uppercase_letter_ratio: float
    all_caps_alias: bool
    single_token: bool
    acronym_in_parentheses: bool


def extract_alias_features(alias: str) -> AliasFeatures:
    value = str(alias or "").strip()
    letters = [char for char in value if char.isalpha()]
    uppercase_letters = sum(1 for char in letters if char.isupper())
    uppercase_ratio = uppercase_letters / len(letters) if letters else 0.0
    parenthetical_values = re.findall(r"\(([^()]*)\)", value)
    acronym_in_parentheses = any(
        token.strip()
        and token.strip().replace("-", "").isalnum()
        and token.strip().upper() == token.strip()
        for token in parenthetical_values
    )
    punctuation_count = sum(
        1 for char in value if not char.isalnum() and not char.isspace()
    )
    words = value.split()
    return AliasFeatures(
        alias=value,
        char_length=len(value),
        utf8_bytes=len(value.encode("utf-8")),
        encoded_length=len(quote(value, safe="")),
        word_count=len(words),
        punctuation_count=punctuation_count,
        parenthesis_count=value.count("(") + value.count(")"),
        ampersand_count=value.count("&"),
        digit_count=sum(1 for char in value if char.isdigit()),
        uppercase_letter_ratio=round(uppercase_ratio, 6),
        all_caps_alias=bool(letters) and uppercase_letters == len(letters),
        single_token=len(words) == 1,
        acronym_in_parentheses=acronym_in_parentheses,
    )


def _numeric_similarity(first: float, second: float) -> float:
    denominator = max(abs(first), abs(second), 1.0)
    return max(0.0, 1.0 - abs(first - second) / denominator)


def _boolean_similarity(first: bool, second: bool) -> float:
    return 1.0 if first == second else 0.0


def structural_similarity(seed_alias: str, candidate_alias: str) -> dict[str, Any]:
    seed = extract_alias_features(seed_alias)
    candidate = extract_alias_features(candidate_alias)
    components = {
        "char_length": _numeric_similarity(seed.char_length, candidate.char_length),
        "encoded_length": _numeric_similarity(
            seed.encoded_length,
            candidate.encoded_length,
        ),
        "word_count": _numeric_similarity(seed.word_count, candidate.word_count),
        "parenthesis_count": _numeric_similarity(
            seed.parenthesis_count,
            candidate.parenthesis_count,
        ),
        "acronym_in_parentheses": _boolean_similarity(
            seed.acronym_in_parentheses,
            candidate.acronym_in_parentheses,
        ),
        "all_caps_alias": _boolean_similarity(
            seed.all_caps_alias,
            candidate.all_caps_alias,
        ),
        "single_token": _boolean_similarity(seed.single_token, candidate.single_token),
        "ampersand_count": _numeric_similarity(
            seed.ampersand_count,
            candidate.ampersand_count,
        ),
        "digit_count": _numeric_similarity(seed.digit_count, candidate.digit_count),
        "punctuation_count": _numeric_similarity(
            seed.punctuation_count,
            candidate.punctuation_count,
        ),
        "uppercase_letter_ratio": _numeric_similarity(
            seed.uppercase_letter_ratio,
            candidate.uppercase_letter_ratio,
        ),
    }
    weights = {
        "char_length": 0.16,
        "encoded_length": 0.10,
        "word_count": 0.14,
        "parenthesis_count": 0.12,
        "acronym_in_parentheses": 0.12,
        "all_caps_alias": 0.08,
        "single_token": 0.06,
        "ampersand_count": 0.06,
        "digit_count": 0.04,
        "punctuation_count": 0.06,
        "uppercase_letter_ratio": 0.06,
    }
    weighted = {
        name: round(components[name] * weight, 6)
        for name, weight in weights.items()
    }
    score = round(sum(weighted.values()), 6)
    return {
        "score": score,
        "seed_features": asdict(seed),
        "candidate_features": asdict(candidate),
        "component_scores": {name: round(value, 6) for name, value in components.items()},
        "weighted_components": weighted,
    }


def similarity_class(score: float) -> str:
    if score >= 0.70:
        return "high"
    if score >= 0.45:
        return "medium"
    if score >= 0.25:
        return "exploratory"
    return "weak"


def rank_alias_candidates(
    *,
    seed_alias: str,
    candidates: Iterable[dict[str, Any]],
    excluded_company_keys: Iterable[str] = (),
) -> list[dict[str, Any]]:
    excluded = {str(value) for value in excluded_company_keys}
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        company_key = str(candidate.get("company_key") or "")
        if company_key in excluded:
            continue
        alias = str(candidate.get("filter_alias") or "").strip()
        if not alias:
            continue
        comparison = structural_similarity(seed_alias, alias)
        ranked.append(
            {
                **candidate,
                "similarity_score": comparison["score"],
                "similarity_class": similarity_class(float(comparison["score"])),
                "similarity": comparison,
            }
        )
    return sorted(
        ranked,
        key=lambda item: (
            -float(item["similarity_score"]),
            str(item["filter_alias"]).casefold(),
            str(item["company_key"]),
        ),
    )


def directed_pair_signature(left_alias: str, right_alias: str) -> dict[str, Any]:
    left = extract_alias_features(left_alias)
    right = extract_alias_features(right_alias)
    joined = f'NOT "{left.alias}" NOT "{right.alias}"'
    return {
        "left": asdict(left),
        "right": asdict(right),
        "left_to_right_char_delta": left.char_length - right.char_length,
        "left_to_right_encoded_delta": left.encoded_length - right.encoded_length,
        "joined_char_length": len(joined),
        "joined_utf8_bytes": len(joined.encode("utf-8")),
        "joined_encoded_length": len(quote(joined, safe="")),
    }
