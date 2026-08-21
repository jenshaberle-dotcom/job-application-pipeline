from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages


ROOT_HOST = "karriere.example.invalid"
ROOT = "https://karriere.example.invalid/"
LISTING = "https://karriere.example.invalid/stellenboerse"
DVINCI_DETAIL = "https://example-karriere.dvinci-hr.com/de/jobs/118/intro"
UNRELATED = "https://other.jobs.personio.de/job/12345"


def test_authorized_listing_can_delegate_one_strict_same_provider_detail() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<a href='{LISTING}'>Stellenbörse</a>", ROOT, 200
        if url == LISTING:
            return (
                "<html><body>dvinci-hr.com "
                f"<a href='{DVINCI_DETAIL}'>Initiativbewerbung</a>"
                "</body></html>",
                LISTING,
                200,
            )
        if url == DVINCI_DETAIL:
            return (
                "<html><title>Initiativbewerbung</title><body>"
                "Jetzt bewerben. Aufgaben, Anforderungen und Ihr Profil. "
                "Wir suchen engagierte Kolleginnen und Kollegen für anspruchsvolle "
                "Beratungsaufgaben und beschreiben hier die konkrete Position."
                "</body></html>",
                DVINCI_DETAIL,
                200,
            )
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(ROOT_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, LISTING, DVINCI_DETAIL]
    assert len(jobs) == 1
    assert jobs[0].final_url == DVINCI_DETAIL
    assert jobs[0].discovery_source == "dvinci_provider_delegated_detail"
    assert jobs[0].proof_kind == "known_detail_and_job_content"


def test_second_hop_does_not_become_generic_cross_host_delegation() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == ROOT:
            return f"<a href='{LISTING}'>Stellenbörse</a>", ROOT, 200
        if url == LISTING:
            return (
                "<html><body>dvinci-hr.com "
                f"<a href='{UNRELATED}'>Other ATS role</a>"
                "</body></html>",
                LISTING,
                200,
            )
        if url == UNRELATED:
            raise AssertionError("different provider host must not be fetched")
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(ROOT_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [ROOT, LISTING]
    assert jobs == []
