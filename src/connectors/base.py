from dataclasses import dataclass
from typing import Any

from src.connectors.capabilities import SourceCapabilities


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


@dataclass(frozen=True)
class RawJobRecord:
    source_name: str
    source_url: str
    external_job_id: str | None
    raw_data: dict[str, Any]


class JobSourceConnector:
    source_name: str
    capabilities: SourceCapabilities

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        raise NotImplementedError
