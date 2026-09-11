"""B-ITE-capable extension of the canonical generic Employer-Origin connector.

B-ITE is attempted first only when the employer itself exposes the provider/tenant
binding.  If no strict B-ITE binding exists, execution falls back unchanged to the
canonical generic product connector.  A recognized B-ITE inventory that cannot
prove target jobs remains fail-closed and does not fall through to weaker logic.
"""

from __future__ import annotations

import logging

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.employer_origin_bite import filter_bite_postings
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
            evidence = dict(evidence)
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


__all__ = ["GenericEmployerOriginProductBiteConnector"]
