from __future__ import annotations

import re
import unicodedata
from typing import Any


LEGAL_SUFFIX_TOKENS = {
    "ag",
    "se",
    "gmbh",
    "kg",
    "kgaa",
    "ohg",
    "ug",
    "eg",
    "mbh",
    "co",
    "company",
    "group",
    "holding",
    "holdings",
    "und",
    "inc",
    "ltd",
    "llc",
    "plc",
}


def normalize_company_key(value: Any) -> str:
    """Normalize company names into a conservative comparison key.

    This helper is intentionally not a full identity-resolution model. It removes
    common legal suffix noise so DB-backed employer-origin candidates can be
    compared with aggregator result-card company names before those cards are
    promoted into another discovery cycle.
    """

    if value is None:
        return ""

    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", " und ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [
        token
        for token in text.split()
        if token and token not in LEGAL_SUFFIX_TOKENS
    ]
    return "_".join(tokens)

def company_key_matches(observed_key: str, candidate_key: str) -> bool:
    """Return whether two normalized company keys represent the same candidate family.

    Exact matches cover the normal case. Prefix matches cover employer group variants
    observed on aggregators, for example ``hdi`` matching ``hdi_global`` or
    ``hdi_vertriebs``. This is intentionally token-bound via underscores so short
    substrings do not match inside unrelated names.
    """

    if not observed_key or not candidate_key:
        return False

    if observed_key == candidate_key:
        return True

    return (
        observed_key.startswith(f"{candidate_key}_")
        or candidate_key.startswith(f"{observed_key}_")
    )


def find_matching_company_key(
    observed_key: str,
    candidate_keys: set[str],
) -> str | None:
    for candidate_key in sorted(candidate_keys, key=len, reverse=True):
        if company_key_matches(observed_key, candidate_key):
            return candidate_key
    return None
