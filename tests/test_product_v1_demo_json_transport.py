from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json

from scripts.run_product_v1_demo_control_center import _json_transport_value


def test_postgres_transport_values_are_json_serializable() -> None:
    payload = {
        "observed_at": datetime(2026, 9, 2, 19, 30, tzinfo=timezone.utc),
        "publication_date": date(2026, 9, 2),
        "overall_quality_score": Decimal("70.40"),
        "nested": (
            {"reviewed_at": datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)},
        ),
    }

    normalized = _json_transport_value(payload)

    assert normalized == {
        "observed_at": "2026-09-02T19:30:00+00:00",
        "publication_date": "2026-09-02",
        "overall_quality_score": 70.4,
        "nested": [{"reviewed_at": "2026-09-02T20:00:00+00:00"}],
    }
    assert json.loads(json.dumps(normalized)) == normalized
