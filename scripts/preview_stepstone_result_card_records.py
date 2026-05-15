"""Preview StepStone result-card records.

This script documents the intended RawJobRecord-shaped output for a future
StepStone result-card spike.

Scope:
- no database writes
- no detail-page fetching
- no pagination
- no production connector implementation
"""

from __future__ import annotations

import json
from typing import Any


def build_example_record() -> dict[str, Any]:
    """Return one example record following the search result connector contract."""
    return {
        "source_name": "stepstone",
        "source_url": "...detail_url...",
        "external_job_id": None,
        "raw_data": {
            "result_card": {
                "title": "...",
                "company_name": "...",
                "location": "...",
                "detail_url": "...",
                "external_job_id_candidate": "...",
            },
            "source_specific": {
                "raw_href": "...",
                "card_html_bytes": 12345,
                "title_id_matches_article_id": True,
                "data_at_fields": {},
            },
            "extraction": {
                "extracted_from": "search_result_page",
                "detail_page_fetched": False,
                "pagination_used": False,
            },
        },
    }


def main() -> None:
    """Print one example StepStone result-card preview record."""
    record = build_example_record()
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
