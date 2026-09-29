from src.search_intelligence.product_v1_demo_learning_sample import (
    DemoLearningSampleStop,
    select_demo_learning_sample,
)


def row(
    job_id: int,
    company: str,
    title: str,
    *,
    facts: int,
    role: bool,
    live: bool = True,
    geo: bool = True,
):
    return {
        "silver_job_id": job_id,
        "company_name": company,
        "title": title,
        "matched_fact_count": facts,
        "candidate_fact_matches": [{"fact_key": f"f-{job_id}"}] if facts else [],
        "role_relevant": role,
        "live_outcome": "seen_active" if live else "unverifiable",
        "geography_eligible": geo,
    }


def test_demo_learning_sample_is_generic_five_plus_five() -> None:
    rows = [
        row(1, "Anchor Corp", "Actuarial Engineer", facts=3, role=False),
        row(2, "Anchor Corp", "Cloud Engineer", facts=3, role=False),
        row(3, "Anchor Corp", "Process Engineer", facts=3, role=False),
        row(4, "Anchor Corp", "Software Engineer", facts=2, role=False),
        row(5, "Anchor Corp", "Consultant", facts=2, role=False),
        row(6, "Anchor Corp", "Other", facts=1, role=False),
        row(10, "ML Co", "AI Platform Engineer", facts=3, role=True),
        row(11, "ML Co", "Sales Specialist", facts=5, role=False),
        row(20, "Data Co", "Data Engineer", facts=4, role=True),
        row(30, "Analytics Co", "Analytics Engineering Lead", facts=5, role=True),
        row(40, "AI Co", "AI Consultant", facts=2, role=False),
        row(50, "Reliability Co", "ML Reliability Engineer", facts=2, role=True),
    ]

    selected = select_demo_learning_sample(rows)

    assert len(selected) == 10
    anchor = [item for item in selected if item["company_name"] == "Anchor Corp"]
    peers = [item for item in selected if item["company_name"] != "Anchor Corp"]
    assert len(anchor) == 5
    assert len({item["company_name"] for item in peers}) == 5
    assert {item["silver_job_id"] for item in peers} == {10, 20, 30, 40, 50}
    assert all(item["silver_job_id"] != 11 for item in selected)



def test_demo_learning_sample_prefers_operator_selected_fi_vacancy_without_job_id_hardcode() -> None:
    rows = [
        row(1, "Anchor Corp", "Actuarial Engineer", facts=3, role=False),
        row(2, "Anchor Corp", "Cloud Engineer", facts=3, role=False),
        row(3, "Anchor Corp", "Process Engineer", facts=3, role=False),
        row(4, "Anchor Corp", "Software Engineer", facts=2, role=False),
        row(5, "Anchor Corp", "Consultant", facts=2, role=False),
        row(6, "Anchor Corp", "Other", facts=1, role=False),
        row(10, "ML Co", "AI Platform Engineer", facts=5, role=True),
        row(20, "Data Co", "Data Engineer", facts=5, role=True),
        row(30, "Analytics Co", "Analytics Engineering Lead", facts=5, role=True),
        row(40, "Reliability Co", "ML Reliability Engineer", facts=4, role=True),
        row(50, "Other AI Co", "AI Consultant", facts=4, role=True),
        row(
            630,
            "Finanz Informatik GmbH & Co. KG",
            "E362/B - AI Engineer / KI-Entwickler (m/w/d)",
            facts=1,
            role=True,
        ),
    ]

    selected = select_demo_learning_sample(rows)
    peers = [item for item in selected if item["company_name"] != "Anchor Corp"]

    assert len(peers) == 5
    assert any(item["silver_job_id"] == 630 for item in peers)
    assert any(
        item["title"] == "E362/B - AI Engineer / KI-Entwickler (m/w/d)"
        for item in peers
    )


def test_demo_learning_sample_fails_closed_without_six_employers() -> None:
    rows = [
        row(index, "Anchor Corp", "Data Job", facts=1, role=True)
        for index in range(1, 7)
    ] + [
        row(10 + index, f"Peer {index}", "AI Engineer", facts=1, role=True)
        for index in range(4)
    ]

    try:
        select_demo_learning_sample(rows)
    except DemoLearningSampleStop as exc:
        assert "at least six eligible employers" in str(exc)
    else:
        raise AssertionError("expected fail-closed demo sample")
