"""CSV schema profiler.

Returns per-column metadata (name, inferred dtype, null fraction, a sample
value) plus row/column counts. Used by /ingest/upload so the user gets a
preview before the file is committed.

Why a hand-rolled profiler instead of pandas?
    The API container already ships psycopg2 + numpy via scikit-learn; pulling
    pandas in just for profiling would bloat the image by ~80MB. The CSV
    surface area is small (header row + N data rows) and Python's stdlib
    `csv` is enough.

Dtype inference is intentionally narrow: int, float, date, bool, string. We
sniff up to MAX_SAMPLE rows per column then commit to the broadest type that
fits every non-null cell. If anything in the column is clearly a string, the
column is a string — there is no automatic promotion to mixed types.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

MAX_SAMPLE = 1000  # cells per column considered for type inference

# Note "0"/"1" are NOT in here on purpose — left to int inference. Treating
# them as bool muddies any numeric column whose first value happens to be 0
# or 1 (e.g. an order count where the smallest is 1).
_BOOL_TRUE = {"true", "t", "yes", "y"}
_BOOL_FALSE = {"false", "f", "no", "n"}

# Cheap ISO-date sniffer. We don't care about wall-clock correctness here;
# we just want to tag obvious YYYY-MM-DD or YYYY-MM-DD HH:MM:SS columns.
_DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}(\s\d{2}:\d{2}(:\d{2})?)?$")


@dataclass
class ColumnProfile:
    name: str
    dtype: str           # int | float | date | bool | string
    null_count: int
    null_pct: float
    sample: str | None


@dataclass
class CsvProfile:
    row_count: int
    column_count: int
    columns: list[ColumnProfile]

    def to_jsonable(self) -> dict:
        return {
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [c.__dict__ for c in self.columns],
        }


def _infer_one(value: str) -> str:
    """Infer the narrowest dtype that fits a single non-empty cell."""
    v = value.strip()
    if not v:
        return "null"
    if v.lower() in _BOOL_TRUE or v.lower() in _BOOL_FALSE:
        return "bool"
    # int before float because "42" matches both regexes
    if re.fullmatch(r"-?\d+", v):
        return "int"
    if re.fullmatch(r"-?\d+(\.\d+)?([eE][+-]?\d+)?", v):
        return "float"
    if _DATE_RX.match(v):
        return "date"
    return "string"


# When two cells in the same column disagree, this table picks the broadest
# type that still fits both. e.g. (int + float) -> float; (int + string) ->
# string. "null" never widens — it falls out of the running.
_WIDEN: dict[tuple[str, str], str] = {
    ("int", "float"): "float",
    ("float", "int"): "float",
}


def _combine(a: str, b: str) -> str:
    if a == "null":
        return b
    if b == "null":
        return a
    if a == b:
        return a
    return _WIDEN.get((a, b), "string")


def profile_csv(content: bytes, *, sample_rows: int = MAX_SAMPLE) -> CsvProfile:
    """Profile a CSV blob in memory. The whole file is scanned for row_count
    but only the first `sample_rows` cells per column drive dtype inference.

    The CSV dialect is sniffed from the first 4KB; if sniffing fails we fall
    back to comma-delimited. Empty files raise ValueError so the caller can
    return a 400 instead of writing a useless row.
    """
    if not content:
        raise ValueError("Empty file")

    try:
        text = content.decode("utf-8-sig")  # strips BOM if present
    except UnicodeDecodeError:
        # Fall back to latin-1 (cp1252-adjacent) — at least we keep going
        # rather than 500ing on a French export saved with the wrong encoding.
        text = content.decode("latin-1")

    sniff_window = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sniff_window)
    except csv.Error:
        dialect = csv.excel  # type: ignore[assignment]

    reader = csv.reader(io.StringIO(text), dialect)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError("Empty file") from exc

    headers = [h.strip() or f"col_{i}" for i, h in enumerate(header)]
    n_cols = len(headers)

    inferred: list[str] = ["null"] * n_cols
    samples: list[str | None] = [None] * n_cols
    null_counts = [0] * n_cols
    row_count = 0

    for row in reader:
        row_count += 1
        # Tolerate ragged rows; missing trailing cells count as nulls.
        for i in range(n_cols):
            value = row[i] if i < len(row) else ""
            if not value.strip():
                null_counts[i] += 1
                continue
            if row_count <= sample_rows:
                inferred[i] = _combine(inferred[i], _infer_one(value))
                if samples[i] is None:
                    samples[i] = value if len(value) <= 80 else value[:77] + "…"

    columns = [
        ColumnProfile(
            name=headers[i],
            # If we never saw a non-null value, call it 'string' — promoting
            # 'null' to a real dtype is something downstream models will do.
            dtype=("string" if inferred[i] == "null" else inferred[i]),
            null_count=null_counts[i],
            null_pct=(null_counts[i] / row_count) if row_count else 0.0,
            sample=samples[i],
        )
        for i in range(n_cols)
    ]
    return CsvProfile(row_count=row_count, column_count=n_cols, columns=columns)


def suggest_table_name(filename: str) -> str:
    """Derive a snake_case dbt staging name from an upload filename.

    Conservative: ASCII alphanumerics + underscores only, lowercased, the
    final ext stripped, prefixed with `stg_user_` so it never collides with
    Olist-native staging models. If the cleaned name is empty (e.g. "_.csv"),
    fall back to 'upload'.
    """
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = base.rsplit(".", 1)[0].lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    if not cleaned:
        cleaned = "upload"
    return f"stg_user_{cleaned}"
