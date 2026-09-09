from __future__ import annotations

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.generic_employer_origin import GenericEmployerOriginConnector
from src.ingestion.generic_origin_bronze_admission import (
    filter_generic_origin_bronze_records,
)


class GenericEmployerOriginProductConnector(GenericEmployerOriginConnector):
    """Production Employer-Origin connector with a separate Bronze job gate.

    The generic layer ``proof=PASS`` gate decides whether the source itself is
    valid and active. This wrapper only decides whether one current observation
    is concrete enough to persist to Bronze. A valid source may therefore
    return zero records without losing source validity.
    """

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        records, final_url = super().fetch_jobs(profile, search_term)
        return filter_generic_origin_bronze_records(records), final_url
