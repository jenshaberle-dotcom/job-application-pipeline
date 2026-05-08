import requests

from src.connectors.base import JobSourceConnector


class GreenhouseConnector(JobSourceConnector):
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, board_token: str) -> None:
        self.board_token = board_token
        self.source_name = f"greenhouse:{board_token}"

    def fetch_jobs(self, profile: dict, search_term: str) -> list[dict]:
        url = f"{self.BASE_URL}/{self.board_token}/jobs"

        response = requests.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

        jobs = payload.get("jobs", [])

        raw_jobs = []

        for job in jobs:
            raw_jobs.append(
                {
                    "source_name": self.source_name,
                    "external_job_id": str(job["id"]),
                    "source_url": job.get("absolute_url"),
                    "raw_data": {
                        "board_token": self.board_token,
                        "job": job,
                    },
                }
            )

        return raw_jobs
