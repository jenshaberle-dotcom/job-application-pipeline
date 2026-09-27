"""Explicit access qualification for job-first market sensors.

Membership in the Census comparison cohort does not imply automation authority.
A source may remain strategically relevant while direct automated access is
withheld until its public access terms and technical path are qualified.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceAccessQualification:
    source: str
    automation_status: str
    reason: str
    public_origin: str | None = None

    @property
    def automation_authorized(self) -> bool:
        return self.automation_status == "authorized"


SOURCE_ACCESS = {
    "bundesagentur_fuer_arbeit": SourceAccessQualification(
        source="bundesagentur_fuer_arbeit",
        automation_status="authorized",
        reason="existing_registered_api_connector",
        public_origin="https://rest.arbeitsagentur.de/",
    ),
    "stepstone": SourceAccessQualification(
        source="stepstone",
        automation_status="authorized",
        reason="existing_limited_result_card_connector",
        public_origin="https://www.stepstone.de/",
    ),
    "goodjobs": SourceAccessQualification(
        source="goodjobs",
        automation_status="withheld",
        reason="direct_automation_requires_explicit_access_authority",
        public_origin="https://goodjobs.eu/",
    ),
    "xing": SourceAccessQualification(
        source="xing",
        automation_status="withheld",
        reason="direct_automation_requires_xing_authorized_interface",
        public_origin="https://www.xing.com/jobs/",
    ),
    "meinestadt": SourceAccessQualification(
        source="meinestadt",
        automation_status="withheld",
        reason="public_terms_explicitly_prohibit_scraping_or_comparable_techniques",
        public_origin="https://www.meinestadt.de/",
    ),
    "get_in_it": SourceAccessQualification(
        source="get_in_it",
        automation_status="withheld",
        reason="public_terms_prohibit_automated_queries_without_explicit_consent",
        public_origin="https://www.get-in-it.de/",
    ),
    "jobvector": SourceAccessQualification(
        source="jobvector",
        automation_status="withheld",
        reason="direct_automation_requires_explicit_interface_or_permission",
        public_origin="https://www.jobvector.de/",
    ),
}


def source_access_qualification(source: str) -> SourceAccessQualification:
    try:
        return SOURCE_ACCESS[source]
    except KeyError as exc:
        raise ValueError(f"No access qualification for Census source: {source}") from exc
