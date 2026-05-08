from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SearchProfile:
    id: int
    profile_name: str
    source_name: str
    search_location: str
    search_radius_km: int
    offer_type: int
    page_size: int


@dataclass(frozen=True)
class SearchTerm:
    search_term: str


@dataclass(frozen=True)
class RawJobRecord:
    source_name: str
    source_url: str
    external_job_id: str | None
    raw_data: dict[str, Any]


class JobSourceConnector:
    source_name: str

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        raise NotImplementedError
