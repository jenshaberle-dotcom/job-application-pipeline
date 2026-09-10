"""Optional open-data evidence for company -> official website resolution.

Wikidata P856 evidence is deliberately non-authoritative. The adapter only returns
candidate URLs plus entity provenance; the existing JAP company-identity scorer and
Employer-Origin proof remain mandatory. Network access is injected so this module is
testable and replaceable, and production callers can fail soft when Wikidata is
unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
MAX_WIKIDATA_ENTITIES = 5


@dataclass(frozen=True)
class OfficialDomainEvidence:
    url: str
    provider: str
    entity_id: str
    entity_label: str
    entity_description: str
    property_id: str = "P856"


JsonRequester = Callable[[str, Mapping[str, str]], Mapping[str, object]]


def _search_entity_ids(payload: Mapping[str, object], *, limit: int) -> tuple[str, ...]:
    raw = payload.get("search")
    if not isinstance(raw, list):
        return ()
    result: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        entity_id = str(item.get("id") or "").strip()
        if entity_id.startswith("Q") and entity_id not in result:
            result.append(entity_id)
        if len(result) >= limit:
            break
    return tuple(result)


def _claim_urls(entity: Mapping[str, object]) -> tuple[str, ...]:
    claims = entity.get("claims")
    if not isinstance(claims, Mapping):
        return ()
    p856 = claims.get("P856")
    if not isinstance(p856, list):
        return ()
    urls: list[str] = []
    for claim in p856:
        if not isinstance(claim, Mapping):
            continue
        mainsnak = claim.get("mainsnak")
        if not isinstance(mainsnak, Mapping):
            continue
        datavalue = mainsnak.get("datavalue")
        if not isinstance(datavalue, Mapping):
            continue
        value = datavalue.get("value")
        if not isinstance(value, str):
            continue
        url = value.strip()
        if url.startswith(("https://", "http://")) and url not in urls:
            urls.append(url)
    return tuple(urls)


def _localized_value(value: object, language: str) -> str:
    if not isinstance(value, Mapping):
        return ""
    candidate = value.get(language) or value.get("en")
    if not isinstance(candidate, Mapping):
        return ""
    return str(candidate.get("value") or "").strip()


def resolve_wikidata_official_domains(
    company_name: str,
    *,
    request_json: JsonRequester,
    language: str = "de",
    max_entities: int = MAX_WIKIDATA_ENTITIES,
) -> tuple[OfficialDomainEvidence, ...]:
    """Return bounded P856 candidates; never decide that any URL is authoritative."""

    name = str(company_name or "").strip()
    if not name:
        return ()
    entity_limit = max(1, min(int(max_entities), MAX_WIKIDATA_ENTITIES))
    search_payload = request_json(
        WIKIDATA_API_URL,
        {
            "action": "wbsearchentities",
            "search": name,
            "language": language,
            "uselang": language,
            "format": "json",
            "limit": str(entity_limit),
            "type": "item",
        },
    )
    entity_ids = _search_entity_ids(search_payload, limit=entity_limit)
    if not entity_ids:
        return ()

    entities_payload = request_json(
        WIKIDATA_API_URL,
        {
            "action": "wbgetentities",
            "ids": "|".join(entity_ids),
            "props": "claims|labels|descriptions",
            "languages": f"{language}|en",
            "format": "json",
        },
    )
    entities = entities_payload.get("entities")
    if not isinstance(entities, Mapping):
        return ()

    result: list[OfficialDomainEvidence] = []
    seen_urls: set[str] = set()
    for entity_id in entity_ids:
        entity = entities.get(entity_id)
        if not isinstance(entity, Mapping):
            continue
        label = _localized_value(entity.get("labels"), language)
        description = _localized_value(entity.get("descriptions"), language)
        for url in _claim_urls(entity):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            result.append(
                OfficialDomainEvidence(
                    url=url,
                    provider="wikidata_p856",
                    entity_id=entity_id,
                    entity_label=label,
                    entity_description=description,
                )
            )
    return tuple(result)


__all__ = [
    "MAX_WIKIDATA_ENTITIES",
    "OfficialDomainEvidence",
    "WIKIDATA_API_URL",
    "resolve_wikidata_official_domains",
]
