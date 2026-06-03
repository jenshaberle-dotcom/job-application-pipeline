from __future__ import annotations

from pathlib import Path

from src.search_intelligence.control_center.renderer import (
    build_template_environment,
    render_template,
)


def test_control_center_jinja_environment_uses_autoescape_and_strict_undefined() -> None:
    environment = build_template_environment()

    assert environment.autoescape("dashboard_foundation.html")
    assert environment.undefined.__name__ == "StrictUndefined"


def test_control_center_jinja_template_escapes_context_values() -> None:
    html = render_template(
        "dashboard_foundation.html",
        {
            "page_title": "Search Intelligence Control Center",
            "eyebrow": "S8A foundation",
            "title": "<unsafe title>",
            "description": "Presentation-only server-rendered template layer.",
            "guardrails": [
                "No business logic in templates",
                "React migration stays possible",
            ],
        },
    )

    assert "&lt;unsafe title&gt;" in html
    assert "<unsafe title>" not in html
    assert "No business logic in templates" in html
    assert "React migration stays possible" in html


def test_control_center_jinja_foundation_keeps_assets_separate() -> None:
    assert Path("src/search_intelligence/control_center/templates/base.html").exists()
    assert Path("src/search_intelligence/control_center/static/control_center.css").exists()
