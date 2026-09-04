from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_bite_employer_origin_probe.py"
SPEC = importlib.util.spec_from_file_location("bite_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_build_payload_matches_observed_bite_contract() -> None:
    payload = probe.build_payload(
        key="a" * 40,
        channel=0,
        locale="de",
        origin="https://example.test/karriere/stellenangebote",
        page_offset=0,
        page_num=1000,
        sort_by="endsOn",
        sort_order="desc",
        filter_key="custom.zuordnung_homepage",
        filter_values=["tenant"],
    )

    assert payload == {
        "key": "a" * 40,
        "channel": 0,
        "locale": "de",
        "sort": {"by": "endsOn", "order": "desc"},
        "origin": "https://example.test/karriere/stellenangebote",
        "page": {"offset": 0, "num": 1000},
        "filter": {"custom.zuordnung_homepage": {"in": ["tenant"]}},
    }


def test_matching_is_structural_and_requires_all_terms() -> None:
    document = {
        "jobPostings": [
            {
                "id": "other",
                "title": "Backend Engineer",
                "location": {"city": "Hannover"},
            },
            {
                "id": "wanted",
                "title": "Machine Learning Engineer / Data Scientist (m/w/d)",
                "location": {"city": "Hannover"},
                "url": "https://provider.example/posting/wanted",
                "endsOn": "2026-10-01",
            },
        ]
    }

    containers = probe.find_candidate_containers(document)
    matches = probe.find_matching_objects(document, ["machine learning", "hannover"])

    assert ("$.jobPostings", 2) in containers
    assert len(matches) == 1
    assert matches[0][1]["id"] == "wanted"


def test_matching_does_not_accept_title_without_location() -> None:
    document = {
        "postings": [
            {
                "id": "wrong-place",
                "title": "Machine Learning Engineer",
                "location": "Berlin",
            }
        ]
    }

    assert probe.find_matching_objects(document, ["machine learning", "hannover"]) == []
