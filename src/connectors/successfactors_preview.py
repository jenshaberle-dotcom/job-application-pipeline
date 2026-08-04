from __future__ import annotations

from datetime import UTC, datetime

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.successfactors import (
    DetailPage,
    ListingCandidate,
    SuccessFactorsConnector,
    build_raw_job_record,
    detail_supports_record,
    extract_listing_candidates,
    normalize_text,
    parse_detail_page,
    select_listing_candidates,
)


def is_concrete_requested_term(value: str) -> bool:
    stripped = value.strip()
    return stripped not in {"", "*"} and bool(normalize_text(stripped))


def preview_candidates(
    candidates: list[ListingCandidate],
    *,
    requested_term: str,
) -> list[ListingCandidate]:
    if not is_concrete_requested_term(requested_term):
        return candidates
    return [candidate for candidate in candidates if candidate.requested_term_match]


class SuccessFactorsPreviewConnector(SuccessFactorsConnector):
    """Read-only SuccessFactors preview with strict concrete-term selection.

    Productive full-fetch ingestion uses the base connector with ``*`` and later local
    multi-term filtering. A review preview with a concrete term must not spend bounded
    detail requests on unrelated profile roles merely because their descriptions contain
    generic terms such as AI, architect or platform.
    """

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        listing_html, final_listing_url, listing_status = self.fetcher(
            self.target.listing_url
        )
        if listing_status >= 400:
            raise RuntimeError(
                f"{self.source_name} listing request failed with status {listing_status}"
            )

        candidates = extract_listing_candidates(
            listing_html,
            final_listing_url,
            target=self.target,
            requested_term=search_term.search_term,
        )
        candidates = preview_candidates(
            candidates,
            requested_term=search_term.search_term,
        )
        selected = select_listing_candidates(
            candidates,
            limit=self.max_detail_pages,
        )

        observed_at_utc = datetime.now(UTC).isoformat()
        accepted: list[tuple[ListingCandidate, DetailPage]] = []

        for candidate in selected:
            detail_html, detail_final_url, detail_status = self.fetcher(candidate.url)
            detail = parse_detail_page(
                requested_url=candidate.url,
                final_url=detail_final_url,
                status_code=detail_status,
                html=detail_html,
            )
            if detail_supports_record(candidate, detail, self.target):
                accepted.append((candidate, detail))

        request_count = 1 + len(selected)
        records = [
            build_raw_job_record(
                candidate=candidate,
                detail=detail,
                target=self.target,
                listing_url=final_listing_url,
                observed_at_utc=observed_at_utc,
                request_count=request_count,
                max_detail_pages=self.max_detail_pages,
            )
            for candidate, detail in accepted
        ]
        return records, final_listing_url
