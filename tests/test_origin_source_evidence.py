from src.search_intelligence.origin_source_evidence import (
    ArtifactCandidate,
    assess_origin_evidence_candidate,
    decide_origin_evidence,
    page_evidence_from_html,
    should_request_llm_adjudication,
)


def _assessment(
    *,
    candidate_id: str,
    url: str,
    company_key: str,
    company_name: str,
    title: str,
    body: str,
    lang: str = "de",
    prior_identity_score: float = 0.9,
):
    candidate = ArtifactCandidate(
        url=url,
        provider="tavily",
        title=title,
        prior_identity_score=prior_identity_score,
        prior_total_score=0.9,
    )
    page = page_evidence_from_html(
        requested_url=url,
        final_url=url,
        status_code=200,
        body=f'<html lang="{lang}"><title>{title}</title><body>{body}</body></html>',
    )
    return assess_origin_evidence_candidate(
        candidate_id=candidate_id,
        candidate=candidate,
        company_key=company_key,
        company_name=company_name,
        page=page,
        target_location="Hannover",
    )


def test_concrete_job_listing_beats_generic_career_landing() -> None:
    landing = _assessment(
        candidate_id="C1",
        url="https://www.hannover-re.com/de/karriere/",
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        title="Karriere bei Hannover Rück SE",
        body="Karriere, Bewerbung und Entwicklung bei Hannover Rück SE.",
    )
    listing = _assessment(
        candidate_id="C2",
        url="https://hannoverre.wd3.myworkdayjobs.com/de-DE/Jobs",
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        title="Hannover Rück SE Jobs",
        body=(
            '<a href="https://hannoverre.wd3.myworkdayjobs.com/de-DE/Jobs/'
            'job/Hannover/Data-Engineer_R123">Data Engineer Hannover</a>'
        ),
    )

    decision = decide_origin_evidence(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        assessments=[landing, listing],
    )

    assert decision.deterministic_decision == "origin_url_candidate_selected"
    assert decision.selected_candidate_id == "C2"
    assert decision.selected_url == listing.final_url
    assert decision.confidence_score < 1.0
    assert listing.job_inventory_state == "job_bearing_proven"
    assert listing.observed_job_count >= 1


def test_short_brand_with_conflicting_entity_descriptor_requires_review() -> None:
    assessment = _assessment(
        candidate_id="C1",
        url="https://jobs.msg.group/jobs/data-engineer-123",
        company_key="msg_systems_ag",
        company_name="msg systems ag",
        title="MSG Solutions GmbH Jobs",
        body=(
            "MSG Solutions GmbH "
            '<a href="/jobs/data-engineer-123">Data Engineer Hannover</a>'
        ),
    )
    decision = decide_origin_evidence(
        company_key="msg_systems_ag",
        company_name="msg systems ag",
        assessments=[assessment],
    )

    assert assessment.entity_fidelity == "ambiguous"
    assert decision.deterministic_decision == "manual_review_required"
    assert "entity_ambiguity" in decision.adjudication_reasons
    assert should_request_llm_adjudication(decision) is True


def test_explicitly_empty_ats_is_not_treated_as_wrong_origin() -> None:
    assessment = _assessment(
        candidate_id="C1",
        url="https://example.jobs.personio.de/",
        company_key="example_gmbh",
        company_name="Example GmbH",
        title="Example GmbH Jobs",
        body="Example GmbH – aktuell keine offenen Stellen.",
    )

    assert assessment.source_grade == "ats_job_listing"
    assert assessment.job_inventory_state == "job_bearing_currently_empty"
    decision = decide_origin_evidence(
        company_key="example_gmbh",
        company_name="Example GmbH",
        assessments=[assessment],
    )
    assert decision.deterministic_decision == "origin_url_candidate_selected"


def test_german_listing_wins_equivalent_english_variant() -> None:
    german = _assessment(
        candidate_id="C1",
        url="https://jobs.x1f.one/de/jobs",
        company_key="x1f",
        company_name="x1F GmbH",
        title="x1F GmbH Jobs",
        body='<a href="/de/jobs/data-engineer-123">Data Engineer Hannover</a>',
        lang="de",
    )
    english = _assessment(
        candidate_id="C2",
        url="https://jobs.x1f.one/en/jobs",
        company_key="x1f",
        company_name="x1F GmbH",
        title="x1F GmbH Jobs",
        body='<a href="/en/jobs/data-engineer-123">Data Engineer Hannover</a>',
        lang="en",
    )

    decision = decide_origin_evidence(
        company_key="x1f",
        company_name="x1F GmbH",
        assessments=[english, german],
    )

    assert decision.assessments[0].candidate_id == "C1"
    assert decision.selected_candidate_id == "C1"
