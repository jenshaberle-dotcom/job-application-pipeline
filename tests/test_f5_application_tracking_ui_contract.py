from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKING = ROOT / "frontend" / "control-center" / "src" / "F5ApplicationTracking.tsx"
STYLES = ROOT / "frontend" / "control-center" / "src" / "f5-application-tracking.css"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_application_tracking_clusters_visible_rows_by_effective_stage() -> None:
    tracking = _text(TRACKING)

    assert 'const GROUP_ORDER: Stage[] = ["prepared", "applied", "reply", "interview", "offer", "closed"]' in tracking
    assert "f5-status-groups" in tracking
    assert "f5-status-group-head" in tracking
    assert "group.applications.length" in tracking
    assert "item.effective_stage === stage" in tracking


def test_attention_banner_is_bound_to_real_review_required_count() -> None:
    tracking = _text(TRACKING)

    assert "application.attention_candidate_count" in tracking
    assert "attentionMessage(application)" in tracking
    assert "separat qualifizierter Evidence" in tracking
    assert "Mindestens ein Mail-Signal ist nicht eindeutig genug" not in tracking


def test_evidence_summary_distinguishes_qualified_from_review_required() -> None:
    tracking = _text(TRACKING)
    styles = _text(STYLES)

    assert 'candidate.requires_review ? "Prüfung nötig" : "qualifiziert"' in tracking
    assert "qualified-evidence" in tracking
    assert "review-required" in tracking
    assert ".f5-status-group-head" in styles


def test_application_cards_surface_bounded_job_identity_metadata() -> None:
    tracking = _text(TRACKING)

    assert "Arbeitgeber-Hinweis" in tracking
    assert "Kommunikations-Domain" in tracking
    assert "Job-/Bewerbungsquelle" in tracking
    assert "Jobtitel aus Mail-Metadaten noch nicht ableitbar" in tracking
    assert "Arbeitgeber aus Mail-Metadaten noch nicht ableitbar" in tracking
    assert "application.counterparty_domain || application.sender_domain" in tracking
    assert "application.source_url" in tracking


def test_application_tracking_defaults_to_compact_rows_with_individual_and_global_expand() -> None:
    tracking = _text(TRACKING)
    styles = _text(STYLES)

    assert "expandedIds" in tracking
    assert "toggleExpanded(application.application_id)" in tracking
    assert "Alle aufklappen" in tracking
    assert "Alle einklappen" in tracking
    assert "f5-compact-row" in tracking
    assert "f5-expanded-body" in tracking
    assert 'aria-expanded={expanded}' in tracking
    assert ".f5-compact-row" in styles
    assert ".f5-expanded-body" in styles
