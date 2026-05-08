import requests

from src.config import BA_API_KEY
from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm


class BundesagenturConnector(JobSourceConnector):
    source_name = "bundesagentur_fuer_arbeit"
    base_url = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        params = {
            "was": search_term.search_term,
            "wo": profile.search_location,
            "umkreis": profile.search_radius_km,
            "page": 1,
            "size": profile.page_size,
            "angebotsart": profile.offer_type,
        }

        headers = {
            "X-API-Key": BA_API_KEY,
        }

        response = requests.get(
            self.base_url,
            params=params,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        jobs = data.get("stellenangebote", [])

        records = []
        for job in jobs:
            source_url = (
                job.get("externeUrl")
                or job.get("url")
                or f"ba://{job.get('refnr')}"
            )

            records.append(
                RawJobRecord(
                    source_name=self.source_name,
                    source_url=source_url,
                    external_job_id=job.get("refnr"),
                    raw_data={
                        "search_profile": {
                            "profile_name": profile.profile_name,
                            "search_term": search_term.search_term,
                            "search_location": profile.search_location,
                            "search_radius_km": profile.search_radius_km,
                            "offer_type": profile.offer_type,
                            "page_size": profile.page_size,
                        },
                        "job": job,
                    },
                )
            )

        return records, response.url
