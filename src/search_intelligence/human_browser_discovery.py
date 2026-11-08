"""Isolated Browser Scout evidence and validation contract for employer discovery.

Discovery provenance is untrusted; a model nomination is never a connector admission.
No database changes, production activation, or scheduler effects.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit

from src.connectors.aggressive_factory import advance_candidate
from src.connectors.connector_extraction import (
    AcquisitionResponse, ats_plan, execute_plan, fingerprint_saved_responses,
)
from src.connectors.hannover_tech_registry_poc import api_for, board_url, family, related, host

MAX_PAGE_BYTES = 2_000_000


def canonical_name(value: object) -> str:
    v = str(value or "").casefold().replace("ß", "ss")
    v = unicodedata.normalize("NFKD", v)
    v = "".join(c for c in v if not unicodedata.combining(c))
    v = re.sub(r"[^a-z0-9]+", " ", v)
    v = re.sub(r"\b(gmbh|ag|se|kg|ug|co|inc|ltd|mbh|holding|group|gruppe)\b", " ", v)
    return " ".join(v.split())


def matching_employer(expected: str, observed: str) -> bool:
    a, b = canonical_name(expected), canonical_name(observed)
    return bool(a and b and (a == b or (len(a) >= 8 and a in b)))


def origin(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("public_https_required")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("no_credentials_or_custom_ports")
    return f"https://{parsed.hostname.lower()}"


@dataclass(frozen=True)
class Observation:
    url: str
    title: str
    text_excerpt: str
    links: tuple[str, ...]
    html: str = ""


@dataclass(frozen=True)
class Company:
    key: str
    name: str
    known_website: str = ""
    location: str = "Region Hannover"


class JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_jsonld = False
        self.parts: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        if tag == "script" and "ld+json" in str(attributes.get("type") or "").lower():
            self.in_jsonld = True
            self.parts = []

    def handle_data(self, data) -> None:
        if self.in_jsonld:
            self.parts.append(data)

    def handle_endtag(self, tag) -> None:
        if tag == "script" and self.in_jsonld:
            self.blocks.append("".join(self.parts))
            self.in_jsonld = False


def jobposting_nodes(document: str) -> list[dict]:
    parser = JsonLdParser()
    parser.feed(document[:MAX_PAGE_BYTES])
    result: list[dict] = []

    def collect(item: object) -> None:
        if isinstance(item, list):
            for child in item:
                collect(child)
        if isinstance(item, dict):
            type_values = item.get("@type", [])
            if isinstance(type_values, str):
                type_values = [type_values]
            if any(str(x).split("/")[-1].casefold() == "jobposting"
                   for x in type_values):
                result.append(item)
            collect(item.get("@graph", []))

    for block in parser.blocks:
        try:
            collect(json.loads(block))
        except (json.JSONDecodeError, TypeError):
            continue
    return result


def valid_jobposting_for(company: Company, observation: Observation) -> list[dict]:
    """A concrete job record with matching hiringOrganization, not just career text."""
    matches = []
    for job in jobposting_nodes(observation.html):
        title = str(job.get("title") or "").strip()
        description = str(job.get("description") or "").strip()
        organization = job.get("hiringOrganization")
        same_as = organization.get("sameAs", "") if isinstance(organization, dict) else ""
        if isinstance(organization, dict):
            organization = organization.get("name")
        if not isinstance(organization, str):
            organization = ""
        job_url = job.get("url")
        if not isinstance(job_url, str) or not job_url.startswith("https://"):
            job_url = observation.url
        if not (title and len(description) >= 30 and matching_employer(
                company.name, organization)):
            continue
        matches.append({"title": title, "url": job_url,
                        "hiring_organization": organization,
                        "hiring_organization_same_as": same_as})
    return matches


def official_link_evidence(company: Company, candidate: str,
                           observations: list[Observation]) -> list[dict]:
    """Require exact observed outbound link from a company-identity-bearing page."""
    if not company.known_website:
        return []
    try:
        official_host = host(origin(company.known_website))
    except ValueError:
        return []
    proof = []
    for observation in observations:
        if host(observation.url) != official_host:
            continue
        if not matching_employer(
            company.name, f"{observation.title} {observation.text_excerpt[:600]}"
        ):
            continue
        linked = [url for url in observation.links if related(candidate, url)]
        for link in linked:
            proof.append({
                "type": "observed_official_career_link",
                "from": observation.url, "to": link,
                "source_sha256": hashlib.sha256(observation.html.encode()).hexdigest(),
            })
    return proof


def verify_portal(company: Company, candidate: str, observations: list[Observation],
                  fetch, catalog: dict) -> dict:
    """Verify at least one job; reuse JAP's existing Factory, do not activate it.

    fetch(url) returns a Page-like object: status, body, url.
    """
    canonical = board_url(candidate)
    if not canonical:
        return {"status": "REJECTED", "reason": "invalid_candidate_url"}
    provider = family(canonical)
    official = official_link_evidence(company, canonical, observations)
    job_evidence: list[dict] = []
    provider_tags: tuple[str, ...] = ()
    api = api_for(canonical)
    responses: dict[str, AcquisitionResponse] = {}
    error = None

    if api and provider in {"greenhouse", "lever"}:
        try:
            response = fetch(api)
            if response.status != 200:
                raise ValueError(f"provider_http_{response.status}")
            if len(response.body.encode()) > MAX_PAGE_BYTES:
                raise ValueError("provider_response_oversized")
            if response.url != api:
                raise ValueError("provider_redirect_not_qualified")
            allowed = tuple(sorted({origin(api), origin(canonical)}))
            first = AcquisitionResponse(api, 200, response.body)
            plan = ats_plan("a" * 64, canonical, api, allowed, provider)
            provider_tags = fingerprint_saved_responses(plan, (first,))
            responses[api] = first

            def get_response(url):
                if url in responses:
                    return responses[url]
                page = fetch(url)
                if page.url != url:
                    raise ValueError("provider_redirect_not_qualified")
                value = AcquisitionResponse(url, page.status, page.body)
                responses[url] = value
                return value

            for job in execute_plan(plan, get_response)[:3]:
                job_evidence.append({"title": job.title, "url": job.source_url})
        except (ValueError, TypeError, KeyError, OSError) as exc:
            error = f"{type(exc).__name__}: {str(exc)[:100]}"

    for observation in observations:
        if (observation.url == candidate or observation.url == canonical
                or related(canonical, observation.url)):
            job_evidence.extend(valid_jobposting_for(company, observation))

    # At least one real job record is necessary for 'active'; an HTTP 200 does not count.
    if not job_evidence:
        return {
            "status": "SOURCE_VERIFIED_JOB_UNPROVEN" if official else "UNRESOLVED",
            "origin_url": canonical, "provider": provider, "job_count": 0,
            "ownership_evidence": official, "error": error,
            "factory_status": "NOT_ATTEMPTED",
        }

    # A JobPosting hiringOrganization matching the requested employer is an
    # additional identity proof. A vendor API inventory alone is insufficient.
    corroborated_hiring_org = False
    if company.known_website:
        try:
            expected = origin(company.known_website)
            corroborated_hiring_org = any(
                item.get("hiring_organization_same_as")
                and host(origin(item["hiring_organization_same_as"])) == host(expected)
                for item in job_evidence if "hiring_organization_same_as" in item
            )
        except (ValueError, TypeError):
            corroborated_hiring_org = False
    if not official and not corroborated_hiring_org:
        return {
            "status": "JOB_FOUND_EMPLOYER_CLAIM_UNCORROBORATED",
            "origin_url": canonical, "provider": provider,
            "job_count": len(job_evidence), "job_sample": job_evidence[:3],
            "factory_status": "NOT_ATTEMPTED",
        }

    evidence_ids = [
        "browser-official:" + hashlib.sha256(json.dumps(
            entry, sort_keys=True).encode()).hexdigest()
        for entry in official
    ]
    if corroborated_hiring_org:
        evidence_ids.append("jobposting-employer:" + hashlib.sha256(json.dumps(
            job_evidence, sort_keys=True).encode()).hexdigest())
    result = {
        "status": "VERIFIED_ACTIVE",
        "origin_url": canonical, "provider": provider,
        "job_count": len(job_evidence),
        "job_sample": job_evidence[:3],
        "ownership_evidence": official,
        "factory_status": "UNSUPPORTED_PROVIDER",
        "runtime_admitted": False, "production_activated": False,
    }
    if provider_tags and evidence_ids:
        source = {
            "company_key": company.key.casefold(),
            "origin_url": canonical,
            "source_type": "employer_origin_ats_backed_career_site",
            "evidence_ids": evidence_ids,
            "fingerprint_tags": list(provider_tags),
            "market_sensor_only": False,
        }
        output = advance_candidate(source, catalog_payload=catalog,
                                   census_digest="a" * 64)
        result["factory_status"] = output["factory_disposition"]
        result["recipe_id"] = output.get("recipe_id")
        result["definition_status"] = output.get("definition_status")
        result["runtime_admitted"] = False
    return result
