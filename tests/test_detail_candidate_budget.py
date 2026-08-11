from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.search_intelligence.detail_candidate_budget import (
    DETAIL_CANDIDATE_SELECTION_VERSION,
    prioritize_detail_candidates,
)


@dataclass(frozen=True)
class Candidate:
    url: str
    text: str


def test_late_exact_target_is_promoted_into_fixed_eight_page_budget() -> None:
    unrelated = [
        Candidate(
            url=f"https://jobs.example.test/Other-Role-{index}-de-j{3000 + index}.html",
            text=f"Unrelated Specialist {index}",
        )
        for index in range(10)
    ]
    target = Candidate(
        url="https://jobs.example.test/Senior-Machine-Learning-Engineer-de-j3999.html",
        text="Senior Machine Learning Engineer (m/w/d)",
    )
    candidates = [*unrelated, target]

    selected, evidence = prioritize_detail_candidates(
        target_title="Senior Machine Learning Engineer (m/w/d)",
        company_name="Example GmbH",
        candidates=candidates,
        limit=8,
    )

    assert len(selected) == 8
    assert selected[0] == target
    assert target in selected
    assert evidence[0].original_index == 10
    assert evidence[0].selected_rank == 1
    assert evidence[0].exact_core_match is True


def test_company_prefix_and_formatting_noise_do_not_hide_near_exact_title() -> None:
    near_exact = Candidate(
        url="https://karriere.example.test/de?id=a1b2c3",
        text="Senior AI Engineer – Dresden / Remote",
    )
    other = Candidate(
        url="https://karriere.example.test/de?id=d4e5f6",
        text="Account Manager Enterprise IT",
    )

    selected, evidence = prioritize_detail_candidates(
        target_title="Example GmbH: Senior AI Engineer (m/w/d) - Dresden oder remote",
        company_name="Example GmbH",
        candidates=[other, near_exact],
        limit=1,
    )

    assert selected == (near_exact,)
    assert evidence[0].link_token_overlap >= 5
    assert evidence[0].relevance_score > 0


def test_title_tokens_in_root_level_ats_url_support_link_text_ranking() -> None:
    url_signal = Candidate(
        url=(
            "https://jobs.example.test/"
            "AI-Platform-Engineer-Developer-Platform-de-j3471.html"
        ),
        text="View vacancy",
    )
    unrelated = Candidate(
        url="https://jobs.example.test/Agile-Tester-de-j3449.html",
        text="View vacancy",
    )

    selected, evidence = prioritize_detail_candidates(
        target_title="AI Platform Engineer - Developer Platform",
        company_name="Example AG",
        candidates=[unrelated, url_signal],
        limit=1,
    )

    assert selected == (url_signal,)
    assert evidence[0].url_token_overlap == 5


def test_completely_uninformative_candidates_keep_discovery_order_and_budget() -> None:
    candidates = [
        Candidate(url=f"https://jobs.example.test/de?id=opaque{index}", text="")
        for index in range(12)
    ]

    selected, evidence = prioritize_detail_candidates(
        target_title="Senior Machine Learning Engineer",
        company_name="Example GmbH",
        candidates=candidates,
        limit=8,
    )

    assert selected == tuple(candidates[:8])
    assert [item.original_index for item in evidence] == list(range(8))
    assert all(item.relevance_score == 0 for item in evidence)


def test_non_positive_budget_fails_closed() -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        prioritize_detail_candidates(
            target_title="Data Engineer",
            company_name="Example GmbH",
            candidates=[],
            limit=0,
        )


def test_selection_contract_version_is_explicit() -> None:
    assert DETAIL_CANDIDATE_SELECTION_VERSION == "DETAIL-BUDGET-001"
