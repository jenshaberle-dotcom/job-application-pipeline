from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

import requests

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities
from src.connectors.stepstone_result_cards import (
    RESULT_CARD_SELECTOR_DESCRIPTION,
    ResultCardFields,
    extract_result_card_fields,
    extract_stepstone_id_from_url,
)


STEPSTONE_BASE_URL = "https://www.stepstone.de"
REQUEST_TIMEOUT_SECONDS = 20

USER_AGENT = (
    "job-application-pipeline-stepstone-connector/0.1 "
    "(limited result-card connector; no detail pages; no crawling)"
)


class StepStoneConnector(JobSourceConnector):
    """Limited StepStone result-card connector.

    This connector intentionally fetches only one search-result page and parses
    result cards. It does not fetch detail pages, does not paginate and does not
    perform broad crawling.
    """

    source_name = "stepstone"

    capabilities = SourceCapabilities(
        supports_keyword=True,
        supports_location=True,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=False,
    )

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        requested_url = build_stepstone_search_url(
            search_term=search_term.search_term,
            search_location=profile.search_location,
        )

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        }

        response = requests.get(
            requested_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        response.raise_for_status()

        observed_at_utc = datetime.now(UTC).isoformat()

        cards = extract_result_card_fields(
            raw_html=response.text,
            final_url=response.url,
        )

        if profile.page_size > 0:
            cards = cards[: profile.page_size]

        records = [
            build_raw_job_record(
                card=card,
                profile=profile,
                search_term=search_term,
                requested_url=requested_url,
                final_search_url=response.url,
                observed_at_utc=observed_at_utc,
            )
            for card in cards
        ]

        return records, response.url


def build_stepstone_search_url(
    search_term: str,
    search_location: str | None,
) -> str:
    term_slug = slugify_stepstone_segment(search_term)

    if search_location:
        location_slug = slugify_stepstone_segment(search_location)
        return f"{STEPSTONE_BASE_URL}/jobs/{term_slug}/in-{location_slug}"

    return f"{STEPSTONE_BASE_URL}/jobs/{term_slug}"


def slugify_stepstone_segment(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value)
    slug = slug.strip("-").lower()

    if not slug:
        raise ValueError("Cannot build StepStone search URL from empty value.")

    return slug


def build_raw_job_record(
    card: ResultCardFields,
    profile: SearchProfile,
    search_term: SearchTerm,
    requested_url: str,
    final_search_url: str,
    observed_at_utc: str,
) -> RawJobRecord:
    detail_url_external_job_id = extract_stepstone_id_from_url(card.detail_url)

    external_job_id = (
        card.external_job_id
        if card.title_id_matches_article_id
        else None
    )

    source_url = card.detail_url or final_search_url

    return RawJobRecord(
        source_name=StepStoneConnector.source_name,
        source_url=source_url,
        external_job_id=external_job_id,
        raw_data=build_raw_data(
            card=card,
            profile=profile,
            search_term=search_term,
            requested_url=requested_url,
            final_search_url=final_search_url,
            observed_at_utc=observed_at_utc,
            detail_url_external_job_id=detail_url_external_job_id,
        ),
    )


def build_raw_data(
    card: ResultCardFields,
    profile: SearchProfile,
    search_term: SearchTerm,
    requested_url: str,
    final_search_url: str,
    observed_at_utc: str,
    detail_url_external_job_id: str | None,
) -> dict[str, Any]:
    return {
        "search_profile": {
            "profile_name": profile.profile_name,
            "search_term": search_term.search_term,
            "search_location": profile.search_location,
            "search_radius_km": profile.search_radius_km,
            "offer_type": profile.offer_type,
            "page_size": profile.page_size,
        },
        "search_context": {
            "requested_url": requested_url,
            "final_search_url": final_search_url,
        },
        "result_card": {
            "title": card.title,
            "company_name": card.company,
            "location": card.location,
            "detail_url": card.detail_url,
            "external_job_id_candidate": card.external_job_id,
            "publication_hint_text": card.publication_hint_text,
            "salary_hint_text": card.salary_hint_text,
            "salary_ui_prompt_text": card.salary_ui_prompt_text,
            "remote_hint_text": card.remote_hint_text,
            "employment_type_hint_text": card.employment_type_hint_text,
        },
        "source_specific": {
            "article_external_job_id": card.external_job_id,
            "detail_url_external_job_id": detail_url_external_job_id,
            "raw_href": card.raw_href,
            "card_html_bytes": card.card_html_bytes,
            "title_id_matches_article_id": card.title_id_matches_article_id,
            "data_at_fields": card.data_at_fields,
            "raw_card_text": card.raw_card_text,
        },
        "extraction": {
            "extracted_from": "search_result_page",
            "detail_page_fetched": False,
            "pagination_used": False,
            "connector_mode": "limited_result_card",
            "selector": RESULT_CARD_SELECTOR_DESCRIPTION,
            "selector_version": "stepstone_result_card_v1",
            "observed_at_utc": observed_at_utc,
        },
        "quality_signals": {
            "has_title": card.title is not None,
            "has_company": card.company is not None,
            "has_location": card.location is not None,
            "has_detail_url": card.detail_url is not None,
            "has_external_job_id_candidate": card.external_job_id is not None,
            "id_match": card.title_id_matches_article_id,
            "has_publication_hint": card.publication_hint_text is not None,
            "has_salary_hint": card.salary_hint_text is not None,
            "has_salary_ui_prompt": card.salary_ui_prompt_text is not None,
            "has_remote_hint": card.remote_hint_text is not None,
            "has_employment_type_hint": card.employment_type_hint_text is not None,
        },
    }
