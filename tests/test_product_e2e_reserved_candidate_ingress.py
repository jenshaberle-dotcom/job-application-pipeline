from __future__ import annotations

import json

import pytest

from scripts.run_product_e2e_candidate_ingress import (
    load_cold_reservation_seed,
)
from src.search_intelligence.product_e2e_golden_path import case_from_seed


def write_reservation(tmp_path, payload):
    path = tmp_path / "reservation.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def test_stepstone_cold_reservation_becomes_aggregator_company_discovery(
    tmp_path,
) -> None:
    path = write_reservation(
        tmp_path,
        {
            "status": "held_out_of_pipeline_for_cold_e2e",
            "must_not_pre_ingest": True,
            "observation": {
                "company_name": "VALUNY GmbH",
                "source_name": "stepstone",
                "title": "Machine Learning Engineer / Data Scientist (m/w/d)",
                "source_url": (
                    "https://www.stepstone.de/"
                    "stellenangebote--example-inline.html"
                ),
            },
        },
    )

    seed = load_cold_reservation_seed(path)
    case = case_from_seed(seed)

    assert seed.company_key == "valuny"
    assert seed.company_name == "VALUNY GmbH"
    assert seed.seed_source_table == "e2e_cold_reservation"
    assert seed.seed_type == "aggregator_company_seed"
    assert seed.url_allowed_for_observation is False

    assert case.discovery_source_class == "aggregator_company_discovery"
    assert case.company_key == "valuny"


def test_public_api_cold_reservation_uses_same_generic_ingress(
    tmp_path,
) -> None:
    path = write_reservation(
        tmp_path,
        {
            "status": "held_out_of_pipeline_for_cold_e2e",
            "must_not_pre_ingest": True,
            "observation": {
                "company_name": "Example Data GmbH",
                "source_name": "bundesagentur_fuer_arbeit",
                "source_url": "https://example.invalid/discovery-only",
            },
        },
    )

    seed = load_cold_reservation_seed(path)
    case = case_from_seed(seed)

    assert case.discovery_source_class == "public_job_api_discovery"


@pytest.mark.parametrize(
    ("status", "must_not_pre_ingest"),
    [
        ("consumed", True),
        ("held_out_of_pipeline_for_cold_e2e", False),
        ("held_out_of_pipeline_for_cold_e2e", None),
    ],
)
def test_invalid_cold_reservation_fails_closed(
    tmp_path,
    status,
    must_not_pre_ingest,
) -> None:
    path = write_reservation(
        tmp_path,
        {
            "status": status,
            "must_not_pre_ingest": must_not_pre_ingest,
            "observation": {
                "company_name": "VALUNY GmbH",
                "source_name": "stepstone",
            },
        },
    )

    with pytest.raises(ValueError):
        load_cold_reservation_seed(path)
