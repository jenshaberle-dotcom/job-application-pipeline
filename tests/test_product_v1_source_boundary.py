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


def test_rankable_refill_is_scoped_to_authorized_recurring_sources() -> None:
    conn = _Connection()

    assert _load_rows(
        conn,
        authorized_sources=["generic_origin:example"],
        limit=30,
    ) == []

    assert "readiness.source_name = ANY(%s)" in conn.last_cursor.sql
    assert "readiness.canonical_source_type = ANY(%s)" not in conn.last_cursor.sql
    assert "readiness.lifecycle_status = 'active_confirmed'" in conn.last_cursor.sql
    assert conn.last_cursor.params == (["generic_origin:example"], 30)


def test_empty_authorized_source_set_cannot_bypass_connector_authority() -> None:
    conn = _Connection()

    assert _load_rows(conn, authorized_sources=[], limit=100) == []

    assert "readiness.source_name = ANY(%s)" in conn.last_cursor.sql
    assert conn.last_cursor.params == ([], 100)
