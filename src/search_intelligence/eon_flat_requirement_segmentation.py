from __future__ import annotations

from html import escape
from typing import Final

from src.search_intelligence.eon_requirement_inventory import description_lines


PROFILE_HEADING: Final = "Your Profile – authentic & open-minded"
END_HEADING: Final = "Our Benefits – smart & useful"

EXACT_PROFILE_STATEMENTS: Final[tuple[str, ...]] = (
    "Extensive professional experience in data engineering positions and a consulting background",
    "Hands-on experience in building end-to-end data solutions",
    (
        "Experience with software development best practices, including version control, "
        "continuous integration and continuous deployment (CI/CD), monitoring, automation "
        "and testing"
    ),
    "Expertise in Kubernetes, Airflow, Kafka, Containerization and Helm Charts",
    (
        "Experience in Microsoft Azure, Infrastructure-as-a-Code as well as building secure "
        "cloud architecture"
    ),
    (
        "Experience with our technology stack which includes Azure Data Factory, Databricks, "
        "Terraform, Python, Spark"
    ),
    "Excellent communication skills engaging various stakeholders matching the audience",
    "Fluent in English and German",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _render_structured_profile() -> str:
    statements = "".join(
        f"<p>{escape(statement)}</p>" for statement in EXACT_PROFILE_STATEMENTS
    )
    return f"<h2>Your Profile</h2>{statements}<h2>What we offer</h2>"


def prepare_eon_requirement_description(description: object) -> object:
    """Restore only the exact known profile blocks from the flattened E.ON pilot text.

    Structured descriptions are returned unchanged. The fallback activates only when the
    stored description normalizes to one long line and contains the exact observed E.ON
    profile and benefits anchors. The profile body must equal the eight employer statements
    observed in the private read-only diagnostic, in the same order and without extra text.
    """

    lines = description_lines(description)
    if len(lines) != 1:
        return description

    flat_text = lines[0]
    _require(
        len(flat_text) >= 1_000,
        "single-line E.ON description is too short for the bounded flattened-page fallback",
    )
    _require(
        flat_text.count(PROFILE_HEADING) == 1,
        "flattened E.ON description must contain the exact profile heading once",
    )
    _require(
        flat_text.count(END_HEADING) == 1,
        "flattened E.ON description must contain the exact benefits heading once",
    )

    profile_start = flat_text.index(PROFILE_HEADING) + len(PROFILE_HEADING)
    profile_end = flat_text.index(END_HEADING)
    _require(
        profile_start < profile_end,
        "flattened E.ON profile and benefits headings are out of order",
    )

    observed_profile_body = flat_text[profile_start:profile_end].strip()
    expected_profile_body = " ".join(EXACT_PROFILE_STATEMENTS)
    _require(
        observed_profile_body == expected_profile_body,
        "flattened E.ON profile body differs from the exact observed employer statements",
    )

    return _render_structured_profile()
