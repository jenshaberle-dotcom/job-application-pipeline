import inspect
import json

from src.search_intelligence.product_v1_application_drafter import (
    _validate_fragment,
)
from src.search_intelligence.product_v1_application_drafter_quality import (
    _quality_schema,
)


def test_strict_provider_schema_avoids_unsupported_unique_items() -> None:
    schema = _quality_schema(
        ("candidate.fact.one", "candidate.fact.two"),
        ("exact vacancy quote one", "exact vacancy quote two"),
    )

    encoded = json.dumps(schema)

    assert "uniqueItems" not in encoded


def test_local_validator_retains_duplicate_reference_boundary() -> None:
    source = inspect.getsource(_validate_fragment)

    assert "len(set(fact_keys)) != len(fact_keys)" in source
    assert "len(set(job_quotes)) != len(job_quotes)" in source
