"""B-ITE-capable extension of the canonical generic Employer-Origin connector.

B-ITE is attempted first only when the employer itself exposes the provider/tenant
binding.  If no strict B-ITE binding exists, execution falls back unchanged to the
canonical generic product connector.  A recognized B-ITE inventory that cannot
prove target jobs remains fail-closed and does not fall through to weaker logic.
"""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.employer_origin_bite import BitePosting, filter_bite_postings
from src.connectors.employer_origin_bite_product import acquire_bite_query_proven_jobs
from src.connectors.generic_employer_origin_product import (
    NEUTRAL_TRIGGER_TERM,
    QUERY_CONTROL_TERM,
    QueryProvenJob,
    GenericEmployerOriginProductConnector,
    _product_record,
    load_company_target_terms,
)
from src.connectors.generic_job_detail_evidence import extract_generic_job_detail_evidence
from src.ingestion.generic_origin_bronze_admission import filter_generic_origin_bronze_records

LOGGER = logging.getLogger(__name__)

_BITE_REMOTE_TRUE = frozenset({"1", "ja", "yes", "true"})
_BITE_REMOTE_FALSE = frozenset({"0", "nein", "no", "false"})


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip(" ,;|")
    return text or None


def _bite_remote_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    if normalized in _BITE_REMOTE_TRUE:
        return True
    if normalized in _BITE_REMOTE_FALSE:
        return False
    return None


def project_bite_accessibility_evidence(
    evidence: dict[str, Any],
    posting: BitePosting,
) -> dict[str, Any]:
    """Add explicit B-ITE inventory accessibility fields to generic detail evidence.

    The employer-authorized B-ITE inventory already carries structured location and
    remote fields.  Preserve those source-declared values in the existing generic
    evidence schema instead of inferring accessibility from free text or adding an
    employer-specific parser.
    """

    projected = deepcopy(evidence)
    raw = posting.raw if isinstance(posting.raw, dict) else {}
    address = raw.get("address")
    address = address if isinstance(address, dict) else {}
    custom = raw.get("custom")
    custom = custom if isinstance(custom, dict) else {}

    locations = [
        text
        for value in projected.get("locations", [])
        if (text := _clean_text(value)) is not None
    ]
    for value in (address.get("city"), custom.get("ort")):
        text = _clean_text(value)
        if text and text.casefold() not in {item.casefold() for item in locations}:
            locations.append(text)

    remote = _bite_remote_value(custom.get("remote"))
    if remote is None:
        existing_remote = projected.get("remote")
        remote = existing_remote if isinstance(existing_remote, bool) else None

    projected["locations"] = locations
    projected["remote"] = remote

    methods = [
        str(value)
        for value in projected.get("methods", [])
        if isinstance(value, str) and value.strip()
    ]
    if locations or remote is not None:
        if "bite_inventory_structured_accessibility" not in methods:
            methods.append("bite_inventory_structured_accessibility")
    projected["methods"] = methods

    field_presence = projected.get("field_presence")
    field_presence = dict(field_presence) if isinstance(field_presence, dict) else {}
    field_presence["locations"] = bool(
        locations or projected.get("structured_locations")
    )
    field_presence["remote"] = remote is not None
    projected["field_presence"] = field_presence

    return projected


def _matching_term(posting, target_terms: list[str]) -> str:
    for term in target_terms:
        if filter_bite_postings((posting,), term):
            return term
    return target_terms[0]


class GenericEmployerOriginProductBiteConnector(GenericEmployerOriginProductConnector):
    """Canonical generic product connector plus strict employer-backed B-ITE support."""

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        if search_term.search_term != NEUTRAL_TRIGGER_TERM:
            return super().fetch_jobs(profile, search_term)

        source = self.candidate_loader(self.company_key)
        target_terms = load_company_target_terms(source.company_key)
        bite = acquire_bite_query_proven_jobs(
            origin_url=source.candidate_url,
            target_terms=target_terms,
            control_term=QUERY_CONTROL_TERM,
        )

        if bite.status == "not_available":
            return super().fetch_jobs(profile, search_term)
        if bite.status != "proven":
            LOGGER.warning(
                "Generic B-ITE product search not admitted: source=%s status=%s reason=%s requests=%s inventory=%s",
                self.source_name,
                bite.status,
                bite.reason,
                bite.request_count,
                bite.inventory_count,
            )
            return [], source.candidate_url

        query_jobs: list[QueryProvenJob] = []
        for item in bite.jobs:
            evidence = extract_generic_job_detail_evidence(
                html=item.raw_body,
                url=item.job.final_url,
                page_title=item.job.title,
            )
            evidence = project_bite_accessibility_evidence(evidence, item.posting)
            evidence["status_code"] = item.job.status_code
            evidence["provider_family"] = "bite"
            evidence["finite_inventory_query_semantics"] = True
            query_jobs.append(
                QueryProvenJob(
                    job=item.job,
                    query=_matching_term(item.posting, target_terms),
                    mechanism="bite_finite_inventory",
                    detail_evidence=evidence,
                )
            )

        records = [
            _product_record(source_name=self.source_name, source=source, item=item)
            for item in query_jobs
        ]
        admitted = filter_generic_origin_bronze_records(records)
        LOGGER.info(
            "Generic B-ITE product search admitted source=%s query_proven=%s bronze=%s requests=%s inventory=%s",
            self.source_name,
            len(query_jobs),
            len(admitted),
            bite.request_count,
            bite.inventory_count,
        )
        return admitted, source.candidate_url


__all__ = [
    "GenericEmployerOriginProductBiteConnector",
    "project_bite_accessibility_evidence",
]
