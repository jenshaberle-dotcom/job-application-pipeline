import requests

from src.config import BA_API_KEY
from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities


class BundesagenturConnector(JobSourceConnector):
    source_name = "bundesagentur_fuer_arbeit"
    base_url = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
    max_pages = 10

    capabilities = SourceCapabilities(
        supports_keyword=True,
        supports_location=True,
        supports_radius=True,
        supports_employment_type=True,
        supports_remote_filter=False,
        supports_pagination=True,
        supports_full_fetch=False,
    )

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        headers = {
            "X-API-Key": BA_API_KEY,
        }

        records: list[RawJobRecord] = []
        seen: set[str] = set()
        first_request_url = self.base_url

        for page in range(1, self.max_pages + 1):
            params = {
                "was": search_term.search_term,
                "wo": profile.search_location,
                "umkreis": profile.search_radius_km,
                "page": page,
                "size": profile.page_size,
                "angebotsart": profile.offer_type,
            }

            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            if page == 1:
                first_request_url = response.url

            data = response.json()
            jobs = data.get("stellenangebote", [])
            if not isinstance(jobs, list):
                raise RuntimeError("Bundesagentur search payload has invalid stellenangebote")

            for job in jobs:
                if not isinstance(job, dict):
                    continue
                external_job_id = job.get("referenznummer") or job.get("refnr")
                source_url = (
                    job.get("externeUrl")
                    or job.get("url")
                    or f"ba://{external_job_id}"
                )
                identity = str(external_job_id or source_url or "")
                if not identity or identity in seen:
                    continue
                seen.add(identity)

                records.append(
                    RawJobRecord(
                        source_name=self.source_name,
                        source_url=source_url,
                        external_job_id=external_job_id,
                        raw_data={
                            "search_profile": {
                                "profile_name": profile.profile_name,
                                "search_term": search_term.search_term,
                                "search_location": profile.search_location,
                                "search_radius_km": profile.search_radius_km,
                                "offer_type": profile.offer_type,
                                "page_size": profile.page_size,
                                "page": page,
                                "page_cap": self.max_pages,
                            },
                            "job": job,
                        },
                    )
                )

            if len(jobs) < profile.page_size:
                break

        return records, first_request_url
