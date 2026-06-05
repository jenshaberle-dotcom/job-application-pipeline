from __future__ import annotations

from src.search_intelligence.origin_url_recovery import (
    RecoveryProbeResult,
    generate_recovery_url_candidates,
    select_recovery_url,
)


def test_recovery_candidates_include_related_group_job_host_for_adesso() -> None:
    candidates = generate_recovery_url_candidates(
        company_key="adesso",
        company_name="adesso SE",
        source_family_candidate="adesso",
        current_url="https://www.adesso.de/de/karriere/jobs/index.html",
    )

    assert "https://jobs.adesso-group.com/" in candidates
    assert "https://jobs.adesso-group.com/" == candidates[0]


def test_recovery_selection_uses_first_reachable_career_like_url() -> None:
    candidates = (
        "https://jobs.example-group.com/",
        "https://careers.example.com/",
    )

    def probe(url: str) -> RecoveryProbeResult:
        if "jobs.example" in url:
            return RecoveryProbeResult(url=url, final_url=url, status_code=404, accepted=False, reason="status=404")
        return RecoveryProbeResult(
            url=url,
            final_url=url,
            status_code=200,
            accepted=True,
            reason="reachable career/job-like URL",
        )

    selected, results = select_recovery_url(candidates, probe=probe)

    assert selected == "https://careers.example.com/"
    assert len(results) == 2
