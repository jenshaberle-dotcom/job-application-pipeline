"""Pure structural similarity helpers for StepStone filter aliases.

The module compares parser-relevant string structure rather than business or
semantic company-name similarity. Similarity is reported per explicit
hypothesis; no aggregate score may automatically select a live probe alias.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import quote


HYPOTHESIS_LENGTH_TOKEN = "length_token_shape"
HYPOTHESIS_ACRONYM_NAME = "acronym_name_shape"
HYPOTHESIS_SYNTAX_ENCODING = "syntax_encoding_shape"
SUPPORTED_HYPOTHESES = (
    HYPOTHESIS_LENGTH_TOKEN,
    HYPOTHESIS_ACRONYM_NAME,
    HYPOTHESIS_SYNTAX_ENCODING,
)


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
    uppercase_token_count: int
    contains_acronym_token: bool
    all_caps_alias: bool
    single_token: bool
    acronym_in_parentheses: bool


def _normalized_token(value: str) -> str:
    return re.sub(r"[^0-9A-Za-zÄÖÜäöüß-]", "", value)


def extract_alias_features(alias: str) -> AliasFeatures:
    value = str(alias or "").strip()
    letters = [char for char in value if char.isalpha()]
    uppercase_letters = sum(1 for char in letters if char.isupper())
    uppercase_ratio = uppercase_letters / len(letters) if letters else 0.0
    parenthetical_values = re.findall(r"\(([^()]*)\)", value)
    acronym_in_parentheses = any(
        token.strip()
        and _normalized_token(token).replace("-", "").isalnum()
        and _normalized_token(token).upper() == _normalized_token(token)
        and sum(char.isalpha() for char in _normalized_token(token)) >= 2
        for token in parenthetical_values
    )
    words = value.split()
    normalized_tokens = [_normalized_token(word) for word in words]
    uppercase_tokens = [
        token
        for token in normalized_tokens
        if token
        and token.upper() == token
        and sum(char.isalpha() for char in token) >= 2
    ]
    punctuation_count = sum(
        1 for char in value if not char.isalnum() and not char.isspace()
    )
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
        uppercase_token_count=len(uppercase_tokens),
        contains_acronym_token=bool(uppercase_tokens),
        all_caps_alias=bool(letters) and uppercase_letters == len(letters),
        single_token=len(words) == 1,
        acronym_in_parentheses=acronym_in_parentheses,
    )


def _numeric_similarity(first: float, second: float) -> float:
    denominator = max(abs(first), abs(second), 1.0)
    return max(0.0, 1.0 - abs(first - second) / denominator)


def _boolean_similarity(first: bool, second: bool) -> float:
    return 1.0 if first == second else 0.0


def _component_scores(seed: AliasFeatures, candidate: AliasFeatures) -> dict[str, float]:
    return {
        "char_length": _numeric_similarity(seed.char_length, candidate.char_length),
        "encoded_length": _numeric_similarity(seed.encoded_length, candidate.encoded_length),
        "word_count": _numeric_similarity(seed.word_count, candidate.word_count),
        "parenthesis_count": _numeric_similarity(
            seed.parenthesis_count,
            candidate.parenthesis_count,
        ),
        "acronym_in_parentheses": _boolean_similarity(
            seed.acronym_in_parentheses,
            candidate.acronym_in_parentheses,
        ),
        "contains_acronym_token": _boolean_similarity(
            seed.contains_acronym_token,
            candidate.contains_acronym_token,
        ),
        "uppercase_token_count": _numeric_similarity(
            seed.uppercase_token_count,
            candidate.uppercase_token_count,
        ),
        "all_caps_alias": _boolean_similarity(seed.all_caps_alias, candidate.all_caps_alias),
        "single_token": _boolean_similarity(seed.single_token, candidate.single_token),
        "ampersand_count": _numeric_similarity(seed.ampersand_count, candidate.ampersand_count),
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


HYPOTHESIS_WEIGHTS: dict[str, dict[str, float]] = {
    HYPOTHESIS_LENGTH_TOKEN: {
        "char_length": 0.30,
        "encoded_length": 0.25,
        "word_count": 0.25,
        "punctuation_count": 0.10,
        "uppercase_letter_ratio": 0.10,
    },
    HYPOTHESIS_ACRONYM_NAME: {
        "contains_acronym_token": 0.30,
        "uppercase_token_count": 0.20,
        "word_count": 0.15,
        "char_length": 0.15,
        "uppercase_letter_ratio": 0.10,
        "acronym_in_parentheses": 0.10,
    },
    HYPOTHESIS_SYNTAX_ENCODING: {
        "encoded_length": 0.25,
        "punctuation_count": 0.20,
        "parenthesis_count": 0.20,
        "acronym_in_parentheses": 0.15,
        "ampersand_count": 0.08,
        "digit_count": 0.04,
        "char_length": 0.08,
    },
}


def structural_similarity(
    seed_alias: str,
    candidate_alias: str,
    *,
    hypothesis: str = HYPOTHESIS_LENGTH_TOKEN,
) -> dict[str, Any]:
    if hypothesis not in SUPPORTED_HYPOTHESES:
        raise ValueError(f"Unsupported similarity hypothesis: {hypothesis}")
    seed = extract_alias_features(seed_alias)
    candidate = extract_alias_features(candidate_alias)
    components = _component_scores(seed, candidate)
    weights = HYPOTHESIS_WEIGHTS[hypothesis]
    weighted = {
        name: round(components[name] * weight, 6)
        for name, weight in weights.items()
    }
    score = round(sum(weighted.values()), 6)
    return {
        "hypothesis": hypothesis,
        "score": score,
        "seed_features": asdict(seed),
        "candidate_features": asdict(candidate),
        "component_scores": {
            name: round(value, 6) for name, value in components.items()
        },
        "weighted_components": weighted,
    }


def similarity_class(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.60:
        return "medium"
    if score >= 0.40:
        return "exploratory"
    return "weak"


def critical_signature_match(seed_alias: str, candidate_alias: str) -> dict[str, Any]:
    seed = extract_alias_features(seed_alias)
    candidate = extract_alias_features(candidate_alias)
    required = {
        "has_parentheses": seed.parenthesis_count > 0,
        "acronym_in_parentheses": seed.acronym_in_parentheses,
        "contains_acronym_token": seed.contains_acronym_token,
    }
    observed = {
        "has_parentheses": candidate.parenthesis_count > 0,
        "acronym_in_parentheses": candidate.acronym_in_parentheses,
        "contains_acronym_token": candidate.contains_acronym_token,
    }
    matches = {
        name: observed[name] == expected
        for name, expected in required.items()
    }
    return {
        "required": required,
        "observed": observed,
        "matches": matches,
        "all_match": all(matches.values()),
    }


def rank_alias_candidates(
    *,
    seed_alias: str,
    candidates: Iterable[dict[str, Any]],
    excluded_company_keys: Iterable[str] = (),
    hypothesis: str = HYPOTHESIS_LENGTH_TOKEN,
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
        comparison = structural_similarity(
            seed_alias,
            alias,
            hypothesis=hypothesis,
        )
        ranked.append(
            {
                **candidate,
                "hypothesis": hypothesis,
                "similarity_score": comparison["score"],
                "similarity_class": similarity_class(float(comparison["score"])),
                "critical_signature": critical_signature_match(seed_alias, alias),
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


def rank_candidates_by_hypothesis(
    *,
    seed_alias: str,
    candidates: Iterable[dict[str, Any]],
    excluded_company_keys: Iterable[str] = (),
) -> dict[str, list[dict[str, Any]]]:
    materialized = list(candidates)
    return {
        hypothesis: rank_alias_candidates(
            seed_alias=seed_alias,
            candidates=materialized,
            excluded_company_keys=excluded_company_keys,
            hypothesis=hypothesis,
        )
        for hypothesis in SUPPORTED_HYPOTHESES
    }


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
