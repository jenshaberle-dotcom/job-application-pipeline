from __future__ import annotations

import re
import unicodedata


EXPLICIT_VACANCY_CLOSURE_MARKERS: tuple[tuple[str, str], ...] = (
    (
        "job_not_available_at_this_time",
        "you can't view this job because it's not available at this time",
    ),
    (
        "job_no_longer_available",
        "this job is no longer available",
    ),
    (
        "position_no_longer_available",
        "this position is no longer available",
    ),
    (
        "stelle_nicht_mehr_verfuegbar",
        "diese stelle ist nicht mehr verfügbar",
    ),
    (
        "stellenausschreibung_nicht_mehr_verfuegbar",
        "diese stellenausschreibung ist nicht mehr verfügbar",
    ),
)


def normalize_page_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    collapsed = re.sub(r"[^0-9a-z]+", " ", without_marks.casefold())
    return re.sub(r"\s+", " ", collapsed).strip()


def explicit_vacancy_closure_marker(response_text: str) -> str | None:
    """Return a canonical marker only for explicit vacancy-unavailable content.

    Generic 404 wording, title mismatch, navigation text and listing absence are
    deliberately not closure authority. This helper recognizes only explicit
    phrases that state the vacancy/position itself is unavailable.
    """

    normalized_response = normalize_page_text(response_text)
    if not normalized_response:
        return None

    for marker_key, marker_text in EXPLICIT_VACANCY_CLOSURE_MARKERS:
        if normalize_page_text(marker_text) in normalized_response:
            return marker_key

    return None
