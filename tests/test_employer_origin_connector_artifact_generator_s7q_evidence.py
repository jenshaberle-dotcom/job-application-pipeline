from scripts.run_employer_origin_connector_artifact_generator import (
    SourceCandidate,
    build_implementation,
    concrete_job_detail_url,
)


def make_candidate() -> SourceCandidate:
    return SourceCandidate(
        id=4,
        company_key="enercity",
        company_name="enercity AG",
        candidate_url="https://www.enercity.de/karriere/jobsuche",
        source_name_candidate="enercity:discovery",
        source_family_candidate="enercity",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="medium",
    )


def test_enercity_jobsuche_urls_are_concrete_job_detail_urls() -> None:
    assert concrete_job_detail_url(
        "https://www.enercity.de/karriere/jobsuche/cloud-infrastructure-devops-engineer-f-m-d-azure-focus-J2026011"
    )
    assert concrete_job_detail_url(
        "https://www.enercity.de/karriere/jobsuche/manager-in-trinkwasserschutz-und-entschaedigungsmanagement-J2026258"
    )
    assert not concrete_job_detail_url("https://www.enercity.de/karriere/arbeiten")
    assert not concrete_job_detail_url("https://www.enercity.de/karriere/wir")


def test_s7q_build_queue_evidence_is_carried_into_generated_artifacts() -> None:
    job_a = (
        "https://www.enercity.de/karriere/jobsuche/"
        "cloud-infrastructure-devops-engineer-f-m-d-azure-focus-J2026011"
    )
    job_b = (
        "https://www.enercity.de/karriere/jobsuche/"
        "manager-in-trinkwasserschutz-und-entschaedigungsmanagement-J2026258"
    )
    context_a = "https://www.enercity.de/karriere/arbeiten"
    context_b = "https://www.enercity.de/karriere/wir"

    implementation = build_implementation(
        make_candidate(),
        {
            "evidence": {
                "connector_candidate_spec": {
                    "detail_evidence": {
                        "detail_urls": [context_a, context_b, job_a, job_b],
                    },
                },
            },
        },
    )

    assert f"KNOWN_DETAIL_URLS = ({job_a!r}, {job_b!r})" in implementation.module_content
    assert context_a not in implementation.module_content
    assert context_b not in implementation.module_content

    assert "Generated from DB-backed approval-gated connector evidence" in implementation.docs_content
    assert "Concrete job-detail evidence carried into the connector candidate" in implementation.docs_content
    assert f"- {job_a}" in implementation.docs_content
    assert f"- {job_b}" in implementation.docs_content
    assert "Broader career-context URLs were present" in implementation.docs_content
    assert f"- {context_a}" in implementation.docs_content
    assert f"- {context_b}" in implementation.docs_content
