"""Machine-readable Product V1 Candidate Fit preference policy."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Mapping


SCHEMA = "product_v1_candidate_fit_policy.v1"
_ALLOWED_WORK_MODELS = frozenset({"remote", "hybrid", "onsite"})
_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class CandidateFitPreferencePolicy:
    policy_version: str
    status: str
    regional_cities: tuple[str, ...]
    remote_countries: tuple[str, ...]
    work_models: tuple[str, ...]
    commute_max_minutes: int | None

    def preference_tags(self) -> tuple[str, ...]:
        tags = {
            *(f"profile-fit.city.{value}" for value in self.regional_cities),
            *(f"profile-fit.country.{value}" for value in self.remote_countries),
            *(f"profile-fit.work-model.{value}" for value in self.work_models),
        }
        if self.commute_max_minutes is not None:
            tags.add(f"profile-fit.commute.max-{self.commute_max_minutes}")
        return tuple(sorted(tags))


def _token(value: object, label: str) -> str:
    text = str(value or "").strip().casefold()
    if _TOKEN_RE.fullmatch(text) is None:
        raise ValueError(f"{label} is invalid")
    return text


def parse_candidate_fit_preference_policy(
    payload: Mapping[str, object],
) -> CandidateFitPreferencePolicy:
    if payload.get("schema") != SCHEMA:
        raise ValueError("Candidate Fit policy schema is invalid")
    policy_version = str(payload.get("policy_version") or "").strip()
    if not policy_version:
        raise ValueError("Candidate Fit policy_version is required")
    status = str(payload.get("status") or "").strip().casefold()
    if status != "approved":
        raise ValueError("Candidate Fit policy must be approved")

    geography = payload.get("geography")
    if not isinstance(geography, Mapping):
        raise ValueError("Candidate Fit geography policy is required")

    raw_cities = geography.get("regional_cities")
    raw_countries = geography.get("remote_countries")
    raw_models = geography.get("work_models")
    if not isinstance(raw_cities, list) or not isinstance(raw_countries, list):
        raise ValueError("Candidate Fit geography lists are invalid")
    if not isinstance(raw_models, list):
        raise ValueError("Candidate Fit work_models must be an array")

    cities = tuple(sorted({_token(value, "regional city") for value in raw_cities}))
    countries = tuple(sorted({_token(value, "remote country") for value in raw_countries}))
    work_models = tuple(sorted({_token(value, "work model") for value in raw_models}))
    if not cities and not countries:
        raise ValueError("Candidate Fit geography policy is empty")
    if not work_models or any(value not in _ALLOWED_WORK_MODELS for value in work_models):
        raise ValueError("Candidate Fit work model policy is invalid")

    raw_commute = geography.get("commute_max_minutes")
    commute: int | None
    if raw_commute is None:
        commute = None
    elif isinstance(raw_commute, int) and 0 <= raw_commute <= 240:
        commute = raw_commute
    else:
        raise ValueError("Candidate Fit commute_max_minutes is invalid")

    return CandidateFitPreferencePolicy(
        policy_version=policy_version,
        status=status,
        regional_cities=cities,
        remote_countries=countries,
        work_models=work_models,
        commute_max_minutes=commute,
    )


def load_candidate_fit_preference_policy(path: Path) -> CandidateFitPreferencePolicy:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, Mapping):
        raise ValueError("Candidate Fit policy root must be an object")
    return parse_candidate_fit_preference_policy(decoded)


__all__ = [
    "CandidateFitPreferencePolicy",
    "SCHEMA",
    "load_candidate_fit_preference_policy",
    "parse_candidate_fit_preference_policy",
]
