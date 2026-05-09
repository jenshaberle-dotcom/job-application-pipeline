import requests

from src.connectors.base import JobSourceConnector, RawJobRecord
from src.connectors.capabilities import SourceCapabilities

class GreenhouseConnector(JobSourceConnector):
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    capabilities = SourceCapabilities(
        supports_keyword=False,
        supports_location=False,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=True,
    )

    def __init__(self, board_token: str) -> None:
        self.board_token = board_token
        self.source_name = f"greenhouse:{board_token}"

    def fetch_jobs(self, profile, search_term) -> tuple[list[RawJobRecord], str]:
        requested_url = f"{self.BASE_URL}/{self.board_token}/jobs"

        response = requests.get(
            requested_url,
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()
        jobs = payload.get("jobs", [])

        records = []

        for job in jobs:
            records.append(
                RawJobRecord(
                    source_name=self.source_name,
                    external_job_id=str(job["id"]),
                    source_url=job.get("absolute_url"),
                    raw_data={
                        "board_token": self.board_token,
                        "job": job,
                    },
                )
            )

        return records, requested_url
