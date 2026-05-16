"""Unit tests for services/profiler.py."""

from __future__ import annotations

import pytest

from services.profiler import profile_csv, suggest_table_name


def test_profile_basic_types():
    csv_bytes = (
        b"order_id,amount,is_paid,order_date,note\n"
        b"1,12.50,true,2024-01-02,hello\n"
        b"2,99,false,2024-01-03,\n"
        b"3,17.25,true,2024-01-04,world\n"
    )
    p = profile_csv(csv_bytes)
    assert p.row_count == 3
    assert p.column_count == 5
    names = [c.name for c in p.columns]
    assert names == ["order_id", "amount", "is_paid", "order_date", "note"]
    dtypes = {c.name: c.dtype for c in p.columns}
    # order_id is int (all ints); amount mixes int+float -> float
    assert dtypes["order_id"] == "int"
    assert dtypes["amount"] == "float"
    assert dtypes["is_paid"] == "bool"
    assert dtypes["order_date"] == "date"
    assert dtypes["note"] == "string"


def test_profile_null_pct():
    csv_bytes = b"a,b\n1,\n2,\n3,x\n"
    p = profile_csv(csv_bytes)
    cols = {c.name: c for c in p.columns}
    assert cols["a"].null_count == 0
    assert cols["a"].null_pct == 0.0
    assert cols["b"].null_count == 2
    assert cols["b"].null_pct == pytest.approx(2 / 3)


def test_profile_mixed_types_promote_to_string():
    csv_bytes = b"x\n1\nabc\n2\n"
    p = profile_csv(csv_bytes)
    assert p.columns[0].dtype == "string"


def test_profile_all_nulls_falls_back_to_string():
    csv_bytes = b"x,y\n,\n,\n"
    p = profile_csv(csv_bytes)
    for c in p.columns:
        assert c.dtype == "string"


def test_profile_empty_file_raises():
    with pytest.raises(ValueError):
        profile_csv(b"")


def test_profile_handles_bom():
    csv_bytes = "﻿foo,bar\n1,2\n".encode("utf-8")
    p = profile_csv(csv_bytes)
    assert [c.name for c in p.columns] == ["foo", "bar"]


def test_profile_handles_ragged_rows():
    """Rows shorter than the header should count as nulls, not crash."""
    csv_bytes = b"a,b,c\n1,2,3\n4,5\n6\n"
    p = profile_csv(csv_bytes)
    assert p.row_count == 3
    cols = {c.name: c for c in p.columns}
    assert cols["c"].null_count == 2
    assert cols["b"].null_count == 1


def test_profile_empty_header_columns_get_synthetic_names():
    csv_bytes = b"a,,c\n1,2,3\n"
    p = profile_csv(csv_bytes)
    assert [c.name for c in p.columns] == ["a", "col_1", "c"]


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("orders.csv", "stg_user_orders"),
        ("/tmp/My Orders 2024.CSV", "stg_user_my_orders_2024"),
        ("___.csv", "stg_user_upload"),
        ("weird---name.csv", "stg_user_weird_name"),
        ("path\\to\\file.csv", "stg_user_file"),
    ],
)
def test_suggest_table_name(filename, expected):
    assert suggest_table_name(filename) == expected
