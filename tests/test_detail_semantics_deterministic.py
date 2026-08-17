from __future__ import annotations

from src.search_intelligence.detail_semantics_deterministic import (
    deterministic_detail_semantics,
    extract_job_postings,
)

DETAIL_URL = "https://jobs.example.com/jobs/42"


def test_extracts_jobposting_from_json_ld_graph() -> None:
    html = """
    <html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
      {"@type":"Organization","name":"Example"},
      {"@type":"JobPosting","title":"Senior Data Engineer"}
    ]}
    </script></head></html>
    """
    postings = extract_job_postings(html)
    assert len(postings) == 1
    assert postings[0]["title"] == "Senior Data Engineer"


def test_structured_jobposting_resolves_role_location_remote_and_skills() -> None:
    html = """
    <html><head><title>Senior Data Engineer | Example</title>
    <script type="application/ld+json">
    {
      "@context":"https://schema.org",
      "@type":"JobPosting",
      "title":"Senior Data Engineer",
      "jobLocation":{"@type":"Place","address":{"addressLocality":"Hannover"}},
      "jobLocationType":"TELECOMMUTE",
      "skills":"Python, SQL"
    }
    </script></head><body>Senior Data Engineer Hannover TELECOMMUTE Python SQL</body></html>
    """
    text = "Senior Data Engineer Example Senior Data Engineer Hannover TELECOMMUTE Python SQL"
    fields, references = deterministic_detail_semantics(
        html=html,
        text=text,
        page_title="Senior Data Engineer | Example",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("role", "seniority", "skills", "location", "remote"),
    )

    assert fields["role"] == "Senior Data Engineer"
    assert fields["seniority"].casefold() == "senior"
    assert tuple(value.casefold() for value in fields["skills"]) == ("python", "sql")
    assert fields["location"].casefold() == "hannover"
    assert fields["remote"] == "TELECOMMUTE"
    assert {reference.field for reference in references} == {
        "role",
        "seniority",
        "skills",
        "location",
        "remote",
    }
    assert all(reference.source_url == DETAIL_URL for reference in references)
    assert all(
        reference.span_start is not None
        and reference.span_end is not None
        and text[reference.span_start : reference.span_end] == reference.evidence
        for reference in references
    )


def test_page_title_is_strong_role_and_seniority_context_without_json_ld() -> None:
    text = "Lead Analytics Engineer | Example Deine Aufgaben umfassen Datenplattformen."
    fields, _references = deterministic_detail_semantics(
        html="<html></html>",
        text=text,
        page_title="Lead Analytics Engineer | Example",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("role", "seniority"),
    )
    assert fields == {"role": "Analytics Engineer", "seniority": "Lead"}


def test_seniority_does_not_infer_from_years_of_experience() -> None:
    text = "Data Engineer. Du bringst mindestens 5 Jahre Berufserfahrung mit."
    fields, _references = deterministic_detail_semantics(
        html="<html></html>",
        text=text,
        page_title="Data Engineer",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("seniority",),
    )
    assert fields == {}


def test_seniority_uses_explicit_labeled_level_context() -> None:
    text = "Karrierestufe: Senior. Data Platform Engineer"
    fields, _references = deterministic_detail_semantics(
        html="<html></html>",
        text=text,
        page_title="Data Platform Engineer",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("seniority",),
    )
    assert fields == {"seniority": "Senior"}


def test_location_requires_structured_title_or_labeled_context() -> None:
    noisy = "Hannover Rück sucht Verstärkung für unser Team in London."
    fields, _references = deterministic_detail_semantics(
        html="<html></html>",
        text=noisy,
        page_title="Data Engineer | Hannover Rück",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("location",),
    )
    assert fields == {}

    labeled = "Arbeitsort: Hannover. Data Engineer"
    fields, _references = deterministic_detail_semantics(
        html="<html></html>",
        text=labeled,
        page_title="Data Engineer",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("location",),
    )
    assert fields == {"location": "Hannover"}


def test_skill_matching_uses_token_boundaries() -> None:
    text = "Wir bauen Maintenance-Tools. Erfahrung mit AI-Plattformen und SQL ist hilfreich."
    fields, _references = deterministic_detail_semantics(
        html="<html></html>",
        text=text,
        page_title="Platform Engineer",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("skills",),
    )
    assert fields == {"skills": ("SQL",)}


def test_remote_phrase_is_grounded_without_location_inference() -> None:
    text = "Wir ermöglichen mobiles Arbeiten und flexible Arbeitszeiten."
    fields, references = deterministic_detail_semantics(
        html="<html></html>",
        text=text,
        page_title="Data Engineer",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("remote",),
    )
    assert fields == {"remote": "mobiles Arbeiten"}
    assert references[0].evidence == "mobiles Arbeiten"


def test_invalid_json_ld_is_ignored_fail_closed() -> None:
    fields, references = deterministic_detail_semantics(
        html='<script type="application/ld+json">{broken</script>',
        text="Unclassified vacancy",
        page_title="Unclassified vacancy",
        detail_url=DETAIL_URL,
        target_location="hannover",
        requested_fields=("role", "location"),
    )
    assert fields == {}
    assert references == ()
