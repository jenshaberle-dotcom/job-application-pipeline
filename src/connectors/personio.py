from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

import requests

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities


REQUEST_TIMEOUT_SECONDS = 20

USER_AGENT = (
    "job-application-pipeline-personio-connector/0.1 "
    "(public XML feed; no detail pages; no crawling)"
)


class PersonioConnector(JobSourceConnector):
    """Minimal public Personio XML connector.

    Defensive acquisition policy:
    - one XML request per configured source target
    - no detail pages
    - no pagination
    - local keyword matching is handled after RawJobRecord creation
    """

    capabilities = SourceCapabilities(
        supports_keyword=False,
        supports_location=False,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=True,
    )

    def __init__(self, target_key: str, language: str = "de") -> None:
        self.target_key = normalize_target_key(target_key)
        self.language = language
        self.host = f"{self.target_key}.jobs.personio.de"
        self.source_name = f"personio:{self.target_key}"

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        requested_url = build_personio_xml_url(
            host=self.host,
            language=self.language,
        )

        response = requests.get(
            requested_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        observed_at_utc = datetime.now(UTC).isoformat()

        positions = extract_positions(response.content)

        records = [
            build_raw_job_record(
                position=position,
                connector=self,
                requested_url=requested_url,
                observed_at_utc=observed_at_utc,
            )
            for position in positions
        ]

        return records, requested_url


def normalize_target_key(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("Personio target key must not be empty.")

    value = value.removeprefix("https://").removeprefix("http://")
    value = value.rstrip("/")

    if "/" in value:
        value = value.split("/", 1)[0]

    value = value.removesuffix(".jobs.personio.de")

    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise ValueError(f"Invalid Personio target key: {value}")

    return value


def build_personio_xml_url(host: str, language: str) -> str:
    return f"https://{host}/xml?language={language}"


def local_name(element: ET.Element) -> str:
    return element.tag.split("}")[-1]


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""

    return re.sub(r"\s+", " ", value).strip()


def first_text(element: ET.Element, names: set[str]) -> str:
    wanted = {name.lower() for name in names}

    for child in element.iter():
        if local_name(child).lower() in wanted:
            value = normalize_whitespace(child.text)
            if value:
                return value

    return ""


def all_text(element: ET.Element) -> str:
    parts = [normalize_whitespace(value) for value in element.itertext()]
    return " ".join(part for part in parts if part)


def search_term_matches(position: ET.Element, search_term: SearchTerm) -> bool:
    term = normalize_whitespace(search_term.search_term).lower()

    if not term:
        return False

    if term == "*":
        return True

    return term in all_text(position).lower()


def element_to_dict(element: ET.Element) -> dict[str, Any] | str:
    children = list(element)
    text = normalize_whitespace(element.text)

    if not children:
        return text

    result: dict[str, Any] = {}

    for child in children:
        key = local_name(child)
        value = element_to_dict(child)

        if key in result:
            existing = result[key]
            if not isinstance(existing, list):
                result[key] = [existing]

            result[key].append(value)
            continue

        result[key] = value

    if text:
        result["_text"] = text

    return result


def extract_positions(xml_content: bytes) -> list[ET.Element]:
    root = ET.fromstring(xml_content)

    return [
        element
        for element in root.iter()
        if local_name(element).lower() == "position"
    ]


def build_raw_job_record(
    position: ET.Element,
    connector: PersonioConnector,
    requested_url: str,
    observed_at_utc: str,
) -> RawJobRecord:
    external_job_id = first_text(position, {"id"}) or None
    title = first_text(position, {"name", "title", "jobtitle"})
    location = first_text(position, {"office", "location", "city"})
    company_name = first_text(position, {"subcompany", "company", "legalentity"})
    department = first_text(position, {"department"})
    employment_type = first_text(position, {"employmenttype", "employment_type"})
    schedule = first_text(position, {"schedule"})
    description = first_text(position, {"jobdescription", "description", "value"})

    source_url = requested_url

    if external_job_id:
        source_url = (
            f"https://{connector.host}/job/{external_job_id}"
            f"?language={connector.language}"
        )

    raw_position = element_to_dict(position)

    return RawJobRecord(
        source_name=connector.source_name,
        source_url=source_url,
        external_job_id=external_job_id,
        raw_data={
            "source_target": {
                "source_family": "personio",
                "target_key": connector.target_key,
                "host": connector.host,
                "language": connector.language,
            },
            "job": {
                "id": external_job_id,
                "title": title,
                "company_name": company_name,
                "location": location,
                "department": department,
                "employment_type": employment_type,
                "schedule": schedule,
                "description": description,
                "source_url": source_url,
            },
            "source_specific": {
                "raw_position": raw_position,
            },
            "extraction": {
                "extracted_from": "public_xml_feed",
                "detail_page_fetched": False,
                "pagination_used": False,
                "local_keyword_filtering_used": False,
                "connector_mode": "personio_public_xml_feed",
                "observed_at_utc": observed_at_utc,
                "requested_url": requested_url,
            },
            "quality_signals": {
                "has_external_job_id": external_job_id is not None,
                "has_title": bool(title),
                "has_company": bool(company_name),
                "has_location": bool(location),
                "has_source_url": bool(source_url),
            },
        },
    )
