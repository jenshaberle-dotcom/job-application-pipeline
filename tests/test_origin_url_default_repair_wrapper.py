from __future__ import annotations

import scripts.run_origin_url_default_repair as default
import scripts.run_origin_url_empirical_cascade as staged


def test_default_entry_point_routes_to_empirical_runtime() -> None:
    assert default.run_default_repair_for_company is staged.run_default_repair_for_company
    assert default.build_parser is staged.build_parser
    assert default.RESULT == staged.RESULT
