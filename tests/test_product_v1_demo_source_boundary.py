from scripts.run_product_v1_rankable_refill_scout import _load_rows


class _Cursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self):
        return []


class _Connection:
    def __init__(self) -> None:
        self.last_cursor = _Cursor()

    def cursor(self):
        return self.last_cursor


def test_demo_scout_uses_product_origin_type_without_recurring_profile_gate() -> None:
    conn = _Connection()

    assert _load_rows(
        conn, authorized_sources=[], limit=100, demo_learning_sample=True
    ) == []

    assert "readiness.canonical_source_type = ANY(%s)" in conn.last_cursor.sql
    assert "readiness.source_name = ANY(%s)" not in conn.last_cursor.sql
    assert "employer_origin_career_site" in conn.last_cursor.params[0]
    assert "employer_origin_ats_backed_career_site" in conn.last_cursor.params[0]
    assert "readiness.lifecycle_status = 'active_confirmed'" in conn.last_cursor.sql


def test_canonical_scout_keeps_recurring_profile_source_scope() -> None:
    conn = _Connection()

    assert _load_rows(conn, authorized_sources=["generic_origin:example"], limit=30) == []

    assert "readiness.source_name = ANY(%s)" in conn.last_cursor.sql
    assert "readiness.canonical_source_type = ANY(%s)" not in conn.last_cursor.sql
    assert conn.last_cursor.params == (["generic_origin:example"], 30)
