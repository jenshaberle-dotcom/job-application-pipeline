from __future__ import annotations

from types import SimpleNamespace

import scripts.run_product_v1_hard_filter_evidence_close as closer


class _NullConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def rollback(self) -> None:
        return None


def _install_common(
    monkeypatch,
    *,
    hard_row_overrides: dict[str, object] | None = None,
    final_url: str = "https://jobs.example.com/42",
    detail_text: str = "Permanent full-time role. English is required.",
    weekly_min: float | None = None,
    weekly_max: float | None = None,
    conflicts: tuple[str, ...] = (),
) -> None:
    hard_row = {
        "silver_job_id": 42,
        "source_name": "origin:example",
        "title": "Data Engineer",
        "capability_fit_status": "passed",
        "deterministic_hard_filter_status": "unknown",
        "hard_filter_status": "unknown",
    }
    hard_row.update(hard_row_overrides or {})
    rank_row = {
        "silver_job_id": 42,
        "source_url": "https://jobs.example.com/42",
        "title": "Data Engineer",
    }

    monkeypatch.setattr(closer.hard_review, "connect", lambda: _NullConn())
    monkeypatch.setattr(closer.ranking_review, "connect", lambda: _NullConn())
    monkeypatch.setattr(closer.hard_review, "ensure_schema", lambda conn: None)
    monkeypatch.setattr(
        closer.hard_review,
        "load_current_rows",
        lambda conn, ids: {42: hard_row},
    )
    monkeypatch.setattr(
        closer.ranking_review,
        "load_current_rows",
        lambda conn, ids: {42: rank_row},
    )
    monkeypatch.setattr(
        closer.hard_review,
        "_unknown_components",
        lambda row: ("weekly_hours",),
    )
    monkeypatch.setattr(closer, "_policy_weekly_window", lambda: (35.0, 40.0))
    monkeypatch.setattr(
        closer,
        "authorized_recurring_employer_origin_sources",
        lambda repository: {"origin:example"},
    )
    monkeypatch.setattr(
        closer,
        "fetch_public_https_detail_text",
        lambda url: (final_url, "Data Engineer", detail_text),
    )
    monkeypatch.setattr(
        closer,
        "extract_product_v1_assessment_evidence",
        lambda **kwargs: SimpleNamespace(
            weekly_hours_min=weekly_min,
            weekly_hours_max=weekly_max,
            conflicted_fields=conflicts,
        ),
    )


def test_same_origin_requires_https_host_and_port_identity() -> None:
    assert closer._same_origin(
        "https://jobs.example.com/42",
        "https://jobs.example.com/42?ref=current",
    )
    assert not closer._same_origin(
        "https://jobs.example.com/42",
        "https://other.example.com/42",
    )
    assert not closer._same_origin(
        "http://jobs.example.com/42",
        "https://jobs.example.com/42",
    )


def test_explicit_full_time_can_close_only_weekly_hours_unknown(monkeypatch) -> None:
    _install_common(monkeypatch)

    reviews, diagnostics = closer.build_evidence_reviews([42])

    assert len(reviews) == 1
    assert reviews[0].silver_job_id == 42
    assert reviews[0].decision == "passed"
    assert "35-40" in reviews[0].rationale
    assert diagnostics == [
        {
            "silver_job_id": 42,
            "status": "reviewable",
            "reason": "explicit_full_time_only_remaining_hours_unknown",
        }
    ]


def test_closer_refuses_more_than_weekly_hours_unknown(monkeypatch) -> None:
    _install_common(monkeypatch)
    monkeypatch.setattr(
        closer.hard_review,
        "_unknown_components",
        lambda row: ("languages", "weekly_hours"),
    )

    reviews, diagnostics = closer.build_evidence_reviews([42])

    assert reviews == ()
    assert diagnostics[0]["reason"] == "unsupported_remaining_unknown_components"


def test_closer_refuses_deterministic_failure(monkeypatch) -> None:
    _install_common(
        monkeypatch,
        hard_row_overrides={
            "deterministic_hard_filter_status": "failed",
            "hard_filter_status": "failed",
        },
    )

    reviews, diagnostics = closer.build_evidence_reviews([42])

    assert reviews == ()
    assert diagnostics[0] == {
        "silver_job_id": 42,
        "status": "not_required",
        "reason": "hard_filter_failed",
    }


def test_closer_refuses_full_time_when_policy_window_does_not_cover_35_to_40(
    monkeypatch,
) -> None:
    _install_common(monkeypatch)
    monkeypatch.setattr(closer, "_policy_weekly_window", lambda: (20.0, 25.0))

    reviews, diagnostics = closer.build_evidence_reviews([42])

    assert reviews == ()
    assert diagnostics[0]["reason"] == "approved_weekly_hours_policy_not_full_time_compatible"


def test_closer_refuses_missing_full_time_evidence(monkeypatch) -> None:
    _install_common(
        monkeypatch,
        detail_text="Permanent role with flexible working arrangements.",
    )

    reviews, diagnostics = closer.build_evidence_reviews([42])

    assert reviews == ()
    assert diagnostics[0]["reason"] == "explicit_full_time_evidence_missing"


def test_closer_refuses_cross_origin_detail_redirect(monkeypatch) -> None:
    _install_common(
        monkeypatch,
        final_url="https://redirect.example.net/42",
    )

    reviews, diagnostics = closer.build_evidence_reviews([42])

    assert reviews == ()
    assert diagnostics[0]["reason"] == "cross_origin_detail_redirect"


def test_numeric_hours_are_refreshed_not_operator_closed(monkeypatch) -> None:
    _install_common(
        monkeypatch,
        detail_text="Permanent full-time role at 38 hours per week.",
        weekly_min=38.0,
        weekly_max=38.0,
    )

    reviews, diagnostics = closer.build_evidence_reviews([42])

    assert reviews == ()
    assert diagnostics[0]["reason"] == "numeric_weekly_hours_requires_assessment_refresh"


def test_closer_has_no_demo_or_job_specific_authority() -> None:
    source = open(closer.__file__, encoding="utf-8").read()

    for forbidden in (
        "TARGET_IDS",
        "DEMO-001",
        "personio:",
        "Hannover Re",
        "Hornetsecurity",
        "silver_job_id = ",
    ):
        assert forbidden not in source

    assert "hard_review.apply_plan" in source
    assert "deterministic_hard_filter_status" in source
    assert "authorized_recurring_employer_origin_sources" in source
    assert "fetch_public_https_detail_text" in source
