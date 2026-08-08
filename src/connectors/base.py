from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from src.connectors.capabilities import SourceCapabilities


EMPLOYER_ORIGIN_CAREER_SITE_SOURCE_TYPE = "employer_origin_career_site"


def separate_generated_employer_origin_acquisition_evidence(
    raw_data: dict[str, Any],
) -> dict[str, Any]:
    """Keep generated gate heuristics as evidence without presenting them as job truth."""
    normalized = deepcopy(raw_data)

    if normalized.get("source_type") != EMPLOYER_ORIGIN_CAREER_SITE_SOURCE_TYPE:
        return normalized

    acquisition_boundary = normalized.get("acquisition_boundary")
    if not isinstance(acquisition_boundary, dict):
        return normalized

    if acquisition_boundary.get("generated_from_gate_evidence") is not True:
        return normalized

    job = normalized.get("job")
    if not isinstance(job, dict):
        job = {}
        normalized["job"] = job

    result_card = normalized.get("result_card")
    if not isinstance(result_card, dict):
        result_card = {}
        normalized["result_card"] = result_card

    acquisition_evidence = normalized.get("acquisition_evidence")
    if not isinstance(acquisition_evidence, dict):
        acquisition_evidence = {}

    profile_terms = job.pop("profile_terms", None)
    job_location = job.pop("location", None)
    result_card_location = result_card.pop("location", None)

    if profile_terms not in (None, [], ""):
        acquisition_evidence["heuristic_profile_terms"] = profile_terms
    if job_location not in (None, ""):
        acquisition_evidence["heuristic_job_location"] = job_location
    if result_card_location not in (None, ""):
        acquisition_evidence["heuristic_result_card_location"] = result_card_location

    if acquisition_evidence:
        normalized["acquisition_evidence"] = acquisition_evidence

    return normalized


@dataclass(frozen=True)
class SearchProfile:
    id: int
    profile_name: str
    source_name: str
    search_location: str | None
    search_radius_km: int | None
    offer_type: int | None
    page_size: int


@dataclass(frozen=True)
class SearchTerm:
    search_term: str
    id: int | None = None


@dataclass(frozen=True)
class RawJobRecord:
    source_name: str
    source_url: str
    external_job_id: str | None
    raw_data: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "raw_data",
            separate_generated_employer_origin_acquisition_evidence(self.raw_data),
        )


class JobSourceConnector:
    source_name: str
    capabilities: SourceCapabilities

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        raise NotImplementedError
