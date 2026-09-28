from __future__ import annotations

from datetime import date, datetime, timezone
import json

import pytest

from scripts.product_v1_control_center_base import _json_default


def test_product_json_boundary_serializes_dates_as_iso_strings() -> None:
    payload = {
        "observed_at": datetime(2026, 9, 28, 21, 7, 0, tzinfo=timezone.utc),
        "valid_from": date(2026, 9, 28),
    }

    encoded = json.dumps(payload, default=_json_default)
    decoded = json.loads(encoded)

    assert decoded == {
        "observed_at": "2026-09-28T21:07:00+00:00",
        "valid_from": "2026-09-28",
    }


def test_product_json_boundary_stays_fail_closed_for_unknown_objects() -> None:
    with pytest.raises(TypeError, match="is not JSON serializable"):
        _json_default(object())
