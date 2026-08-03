from __future__ import annotations

import scripts.run_origin_url_adaptive_repair as adaptive
import scripts.run_origin_url_default_repair as default


def test_default_entry_point_routes_to_adaptive_runtime() -> None:
    assert default.run_default_repair_for_company is adaptive.run_default_repair_for_company
    assert default.build_parser is adaptive.build_parser
    assert default.RESULT == adaptive.RESULT
