"""
Unit tests for the SQL safety validator in api/routers/ask.py.
Pure-function tests — no DB, no LLM.
"""

import pytest
from routers.ask import _strip_fences, validate_sql


class TestStripFences:
    def test_no_fence_passthrough(self):
        sql = "SELECT 1"
        assert _strip_fences(sql) == "SELECT 1"

    def test_strips_sql_fence(self):
        sql = "```sql\nSELECT 1\n```"
        assert _strip_fences(sql) == "SELECT 1"

    def test_strips_bare_fence(self):
        sql = "```\nSELECT 1\n```"
        assert _strip_fences(sql) == "SELECT 1"

    def test_handles_extra_whitespace(self):
        sql = "  ```sql\n  SELECT 1\n```  "
        assert _strip_fences(sql).strip() == "SELECT 1"


class TestValidateSql:
    def test_accepts_select(self):
        assert validate_sql("SELECT * FROM gold.fct_orders") is None

    def test_accepts_with(self):
        assert validate_sql(
            "WITH t AS (SELECT 1 AS a) SELECT a FROM t"
        ) is None

    def test_rejects_empty(self):
        assert validate_sql("") is not None
        assert validate_sql("   ") is not None

    def test_rejects_insert(self):
        assert validate_sql("INSERT INTO t VALUES (1)") is not None

    def test_rejects_update(self):
        assert validate_sql("UPDATE gold.fct_orders SET price = 0") is not None

    def test_rejects_delete(self):
        assert validate_sql("DELETE FROM gold.fct_orders") is not None

    def test_rejects_drop(self):
        assert validate_sql("DROP TABLE gold.fct_orders") is not None

    @pytest.mark.parametrize("forbidden", [
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT rolname FROM pg_authid",
        "SELECT * FROM pg_shadow",
        "SELECT * FROM pg_user",
        "SELECT * FROM pg_roles",
        "SELECT * FROM pg_stat_activity",
        "SELECT table_name FROM information_schema.tables",
        "SELECT * FROM INFORMATION_SCHEMA.columns",
    ])
    def test_rejects_system_catalogs(self, forbidden: str):
        err = validate_sql(forbidden)
        assert err is not None
        assert "restricted" in err.lower()

    def test_rejects_multi_statement(self):
        err = validate_sql("SELECT 1; DROP TABLE t")
        assert err is not None
        assert "multi" in err.lower()

    def test_allows_trailing_semicolon(self):
        # A single trailing ';' should be tolerated
        assert validate_sql("SELECT 1;") is None

    def test_rejects_copy(self):
        assert validate_sql("SELECT * FROM gold.fct_orders; COPY gold.fct_orders TO '/tmp/x.csv'") is not None

    def test_rejects_grant(self):
        # GRANT inside a CTE-shaped string — still flagged
        assert validate_sql("SELECT 1 WHERE 'GRANT ALL' = 'GRANT ALL'") is not None
