from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities


class StepStoneConnector(JobSourceConnector):
    """Prepared connector skeleton for StepStone.

    StepStone is intentionally prepared as a separate connector because
    commercial job portals are technically and legally more sensitive than
    public APIs or ATS job boards.
    """

    source_name = "stepstone"

    capabilities = SourceCapabilities(
        supports_keyword=True,
        supports_location=True,
        supports_radius=True,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=True,
        supports_full_fetch=False,
    )

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        raise NotImplementedError(
            "StepStone connector is prepared but not implemented yet."
        )
