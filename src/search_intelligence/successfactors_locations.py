from __future__ import annotations

from dataclasses import asdict, dataclass
import re


_LOCATION_FIELD = re.compile(
    r"\b(?:Location|Standort|Ort):\s*(?P<value>.+?)"
    r"(?=\s+(?:Function area|Funktionsbereich|Job Req ID|Contract type|"
    r"Working time|Company|Location|Standort|Ort|Apply now|Jetzt bewerben|"
    r"Do you have questions|Haben Sie Fragen):|$)",
    flags=re.IGNORECASE,
)
_COUNTRY_PAIR = re.compile(
    r"(?P<city>[A-ZÄÖÜ][A-Za-zÀ-ÖØ-öø-ÿ .()'\-/]{1,79}?),\s*"
    r"(?P<country>[A-Z]{2})\b"
)
_BLOCKED_LOCATION_VALUES = {
    "flexible",
    "home office",
    "homeoffice",
    "hybrid",
    "remote",
    "work from home",
}


@dataclass(frozen=True)
class SuccessFactorsLocationEvidence:
    city: str
    country: str
    evidence_source: str
    evidence_text: str

    def canonical_payload(self) -> dict[str, str]:
        return asdict(self)


def _clean_city(value: str) -> str | None:
    city = " ".join(value.strip(" ,;|").split())
    if not city or len(city) > 80:
        return None
    if city.casefold() in _BLOCKED_LOCATION_VALUES:
        return None
    if any(character.isdigit() for character in city):
        return None
    if ":" in city or "|" in city:
        return None
    return city


def _deduplicate(
    locations: list[SuccessFactorsLocationEvidence],
) -> tuple[SuccessFactorsLocationEvidence, ...]:
    result: list[SuccessFactorsLocationEvidence] = []
    seen: set[tuple[str, str]] = set()
    for location in locations:
        key = (location.city.casefold(), location.country.casefold())
        if key in seen:
            continue
        seen.add(key)
        result.append(location)
    return tuple(result)


def parse_location_field(
    value: str,
    *,
    default_country: str = "DE",
) -> tuple[SuccessFactorsLocationEvidence, ...]:
    evidence_text = " ".join(value.split()).strip(" ,;|")
    if not evidence_text:
        return ()

    pair_matches = list(_COUNTRY_PAIR.finditer(evidence_text))
    if pair_matches:
        paired: list[SuccessFactorsLocationEvidence] = []
        for match in pair_matches:
            city = _clean_city(match.group("city"))
            if city is None:
                continue
            paired.append(
                SuccessFactorsLocationEvidence(
                    city=city,
                    country=match.group("country").upper(),
                    evidence_source="successfactors_detail_location_field",
                    evidence_text=evidence_text,
                )
            )
        return _deduplicate(paired)

    locations: list[SuccessFactorsLocationEvidence] = []
    for raw_city in re.split(r"\s*[,;]\s*", evidence_text):
        city = _clean_city(raw_city)
        if city is None:
            continue
        locations.append(
            SuccessFactorsLocationEvidence(
                city=city,
                country=default_country.upper(),
                evidence_source="successfactors_detail_location_field",
                evidence_text=evidence_text,
            )
        )
    return _deduplicate(locations)


def extract_successfactors_locations(
    detail_text: str,
    *,
    default_country: str = "DE",
) -> tuple[SuccessFactorsLocationEvidence, ...]:
    """Extract only explicit SuccessFactors location metadata fields.

    The visible-text connector normalizes HTML whitespace. This parser therefore
    binds to labelled metadata fields instead of guessing locations from prose.
    Multiple rendered variants are unioned and deterministically deduplicated.
    """
    normalized_text = " ".join(detail_text.split())
    if not normalized_text:
        return ()

    locations: list[SuccessFactorsLocationEvidence] = []
    for match in _LOCATION_FIELD.finditer(normalized_text):
        locations.extend(
            parse_location_field(
                match.group("value"),
                default_country=default_country,
            )
        )
    return _deduplicate(locations)
