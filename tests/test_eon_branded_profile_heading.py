from __future__ import annotations

import pytest

from src.search_intelligence.eon_requirement_inventory import (
    build_eon_requirement_inventory,
    description_lines,
)


TITLE = "(Senior) Data Engineer Data & AI (f/m/d)"
EXPERIENCE = (
    "Extensive professional experience in data engineering positions "
    "and a consulting background."
)
LANGUAGE = "Fluent in English and German."


def _description(heading: str) -> str:
    return (
        "<h2>Your Role – meaningful & rewarding</h2>"
        "<p>Build operational data-driven solutions.</p>"
        f"<h2>{heading}</h2>"
        f"<ul><li>{EXPERIENCE}</li><li>{LANGUAGE}</li></ul>"
        "<h2>Our Benefits – smart & useful</h2>"
        "<p>Benefits must remain outside the inventory.</p>"
    )


@pytest.mark.parametrize(
    "separator",
    ["–", "—"],
)
def test_accepts_exact_eon_branded_profile_heading(separator: str) -> None:
    inventory = build_eon_requirement_inventory(
        description=_description(
            f"Your Profile {separator} authentic & open-minded\u200b"
        ),
        title=TITLE,
    )

    assert inventory.section_heading == "Your Profile"
    assert [statement.text for statement in inventory.statements] == [
        EXPERIENCE,
        LANGUAGE,
    ]


def test_branded_tagline_is_not_emitted_as_requirement_statement() -> None:
    inventory = build_eon_requirement_inventory(
        description=_description("Your Profile – authentic & open-minded\ufeff"),
        title=TITLE,
    )

    assert all("authentic" not in statement.text.casefold() for statement in inventory.statements)
    assert len(inventory.statements) == 2


def test_line_normalization_removes_unicode_format_characters_only() -> None:
    lines = description_lines(
        "<h2>Your Profile\u200b – authentic & open-minded\ufeff</h2>"
        f"<p>{EXPERIENCE}</p>"
    )

    assert lines == (
        "Your Profile – authentic & open-minded",
        EXPERIENCE,
    )


@pytest.mark.parametrize(
    "heading",
    [
        "Your Profile - authentic & open-minded",
        "Your Profile – energetic & curious",
    ],
)
def test_unknown_or_ascii_hyphen_branding_remains_fail_closed(heading: str) -> None:
    with pytest.raises(ValueError, match="no recognized profile section"):
        build_eon_requirement_inventory(
            description=_description(heading),
            title=TITLE,
        )


def test_colon_still_introduces_real_first_statement() -> None:
    inventory = build_eon_requirement_inventory(
        description=(
            f"<p>Your Profile: {EXPERIENCE}</p>"
            f"<p>{LANGUAGE}</p>"
            "<p>What we offer</p>"
        ),
        title=TITLE,
    )

    assert inventory.section_heading == "Your Profile"
    assert [statement.text for statement in inventory.statements] == [
        EXPERIENCE,
        LANGUAGE,
    ]
