from __future__ import annotations

import pytest

from src.search_intelligence.runtime_listing_interaction import (
    InteractionBudget,
    InteractionProgress,
    VisibleListingControl,
    control_fingerprint,
    select_next_listing_interaction,
)


def _control(
    text: str,
    *,
    role: str = "button",
    aria_label: str = "",
    href: str = "",
    context_text: str = "",
    visible: bool = True,
    enabled: bool = True,
) -> VisibleListingControl:
    return VisibleListingControl(
        role=role,
        text=text,
        aria_label=aria_label,
        href=href,
        context_text=context_text,
        visible=visible,
        enabled=enabled,
    )


def test_prefers_load_more_over_next_and_open_jobs() -> None:
    controls = (
        _control("Open jobs", role="link", href="/careers/jobs"),
        _control("Next page", context_text="Job results"),
        _control("Load more jobs"),
    )

    decision = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://careers.example.com/jobs",
        controls=controls,
    )

    assert decision.action == "click"
    assert decision.control_kind == "load_more"
    assert decision.reason_code == "visible_load_more_control"
    assert decision.no_product_authority is True
    assert decision.control_fingerprint == control_fingerprint(controls[2])


def test_open_jobs_control_is_allowed_from_authorized_career_page() -> None:
    control = _control("View jobs", role="link", href="/jobs")

    decision = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/careers",
        controls=(control,),
    )

    assert decision.action == "click"
    assert decision.control_kind == "open_jobs"


def test_generic_load_more_requires_job_context() -> None:
    without_context = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/about",
        controls=(_control("Load more", context_text="News"),),
        budget=InteractionBudget(max_total_actions=1, max_click_actions=1, max_scroll_actions=0),
    )
    with_context = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/careers/jobs",
        controls=(_control("Load more"),),
        budget=InteractionBudget(max_total_actions=1, max_click_actions=1, max_scroll_actions=0),
    )

    assert without_context.action == "stop"
    assert without_context.reason_code == "no_eligible_visible_listing_interaction"
    assert with_context.action == "click"
    assert with_context.control_kind == "load_more"


def test_plain_next_requires_job_context() -> None:
    rejected = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/about",
        controls=(_control("Next"),),
        budget=InteractionBudget(max_total_actions=1, max_click_actions=1, max_scroll_actions=0),
    )
    accepted = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/jobs",
        controls=(_control("Next"),),
        budget=InteractionBudget(max_total_actions=1, max_click_actions=1, max_scroll_actions=0),
    )

    assert rejected.action == "stop"
    assert accepted.action == "click"
    assert accepted.control_kind == "next_page"


def test_apply_login_filter_and_hidden_controls_fail_closed() -> None:
    controls = (
        _control("Apply now"),
        _control("Sign in"),
        _control("Filter jobs"),
        _control("Load more jobs", visible=False),
        _control("Next page", enabled=False),
    )

    decision = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/jobs",
        controls=controls,
        budget=InteractionBudget(max_total_actions=1, max_click_actions=1, max_scroll_actions=0),
    )

    assert decision.action == "stop"
    assert decision.reason_code == "no_eligible_visible_listing_interaction"


def test_non_https_explicit_href_is_not_click_authority() -> None:
    decision = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/careers",
        controls=(_control("Open jobs", role="link", href="http://jobs.example.com"),),
        budget=InteractionBudget(max_total_actions=1, max_click_actions=1, max_scroll_actions=0),
    )

    assert decision.action == "stop"


def test_repeated_control_fingerprint_is_not_clicked_twice() -> None:
    first = _control("Load more jobs")
    second = _control("Next page", context_text="Jobs")
    progress = InteractionProgress(
        total_actions=1,
        click_actions=1,
        scroll_actions=0,
        attempted_control_fingerprints=(control_fingerprint(first),),
    )

    decision = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/jobs",
        controls=(first, second),
        progress=progress,
    )

    assert decision.action == "click"
    assert decision.control_kind == "next_page"
    assert decision.control_fingerprint == control_fingerprint(second)


def test_scroll_is_single_bounded_fallback_when_no_control_is_eligible() -> None:
    first = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/jobs",
        controls=(),
    )
    after_scroll = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/jobs",
        controls=(),
        progress=InteractionProgress(total_actions=1, click_actions=0, scroll_actions=1),
    )

    assert first.action == "scroll"
    assert first.reason_code == "bounded_listing_scroll_probe"
    assert after_scroll.action == "stop"
    assert after_scroll.reason_code == "no_eligible_visible_listing_interaction"


def test_unauthorized_page_cannot_click_or_scroll() -> None:
    decision = select_next_listing_interaction(
        page_authorized=False,
        page_url="https://unbound.example/jobs",
        controls=(_control("Load more jobs"),),
    )

    assert decision.action == "stop"
    assert decision.reason_code == "page_not_authorized"


def test_total_action_budget_stops_before_another_interaction() -> None:
    progress = InteractionProgress(
        total_actions=3,
        click_actions=2,
        scroll_actions=1,
        attempted_control_fingerprints=("a", "b"),
    )

    decision = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/jobs",
        controls=(_control("Next page"),),
        progress=progress,
    )

    assert decision.action == "stop"
    assert decision.reason_code == "interaction_budget_exhausted"


def test_inconsistent_progress_fails_closed() -> None:
    decision = select_next_listing_interaction(
        page_authorized=True,
        page_url="https://www.example.com/jobs",
        controls=(_control("Load more jobs"),),
        progress=InteractionProgress(total_actions=2, click_actions=1, scroll_actions=0),
    )

    assert decision.action == "stop"
    assert decision.reason_code == "invalid_interaction_progress"


def test_control_fingerprint_redacts_secret_like_query_values() -> None:
    first = _control(
        "Open jobs",
        role="link",
        href="https://jobs.example.com/jobs?tenant=acme&token=secret-one",
    )
    second = _control(
        "Open jobs",
        role="link",
        href="https://jobs.example.com/jobs?tenant=acme&token=secret-two",
    )

    assert control_fingerprint(first) == control_fingerprint(second)


def test_invalid_budget_configuration_raises() -> None:
    with pytest.raises(ValueError, match="max_total_actions"):
        select_next_listing_interaction(
            page_authorized=True,
            page_url="https://www.example.com/jobs",
            controls=(),
            budget=InteractionBudget(max_total_actions=0),
        )
