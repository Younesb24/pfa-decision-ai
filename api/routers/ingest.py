"""Ingest router — Day 12.

POST /ingest/upload accepts a CSV upload, profiles its schema, writes the
bytes under data/ingest/<source_id>/raw.csv, and records a row in
governance.source_registry. The dbt scaffold step (auto-generate a staging
model file) is deferred — the registry entry captures the suggested table
name so a follow-up job can pick it up offline.

GET /ingest/sources returns the registry feed for the /ingest dashboard.

Gating: `ops+` (this surface mutates the data lake). Wired at the main.py
include_router call so a future endpoint under /ingest inherits the guard.
"""

from __future__ import annotations

import os
from pathlib import Path

from db import get_db
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from psycopg2.extras import Json
from pydantic import BaseModel

from services.profiler import profile_csv, suggest_table_name

router = APIRouter(prefix="/ingest", tags=["Ingest"])

# Hard cap so a single upload can't OOM the box. 200 MB is well above any
# realistic CSV a marketplace ops user would attach — bigger payloads should
# go through a proper batch path (S3 + Dagster), not the API.
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


# ── Schemas ─────────────────────────────────────────────────────────────

class ColumnPreview(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float
    sample: str | None = None


class UploadResponse(BaseModel):
    source_id: int
    original_filename: str
    storage_path: str
    size_bytes: int
    row_count: int
    column_count: int
    suggested_table: str
    columns: list[ColumnPreview]


class SourceListEntry(BaseModel):
    id: int
    uploaded_at: str
    original_filename: str
    size_bytes: int
    row_count: int | None
    column_count: int | None
    suggested_table: str | None
    status: str
    error: str | None = None


class SourceListResponse(BaseModel):
    sources: list[SourceListEntry]


# ── Helpers ─────────────────────────────────────────────────────────────

def _ingest_root() -> Path:
    """Where uploaded blobs go. Override with INGEST_ROOT for tests/prod."""
    root = Path(os.getenv("INGEST_ROOT", "data/ingest"))
    root.mkdir(parents=True, exist_ok=True)
    return root


# ── Endpoints ───────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    name_lower = file.filename.lower()
    if not name_lower.endswith(".csv"):
        # Parquet is on the Day 12 roadmap but not in this slice — we'd need
        # pyarrow in the API image and a parallel profiler.
        raise HTTPException(
            status_code=415,
            detail="Only .csv uploads are accepted in this build",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (limit {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )

    try:
        profile = profile_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    suggested = suggest_table_name(file.filename)

    # Insert the registry row first so we have an id to namespace the blob
    # under. If the disk write later fails, we mark the row failed; we never
    # leave a row pointing at a path that doesn't exist.
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO governance.source_registry (
                    original_filename, storage_path, content_type, size_bytes,
                    row_count, column_count, schema_profile, suggested_table
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    file.filename,
                    "",  # placeholder; updated below
                    file.content_type,
                    len(content),
                    profile.row_count,
                    profile.column_count,
                    Json(profile.to_jsonable()),
                    suggested,
                ),
            )
            source_id = cur.fetchone()["id"]
            storage_path = str(Path("data/ingest") / str(source_id) / "raw.csv")
            cur.execute(
                "UPDATE governance.source_registry SET storage_path = %s WHERE id = %s",
                (storage_path, source_id),
            )
        conn.commit()

    target = _ingest_root() / str(source_id) / "raw.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(content)
    except OSError as exc:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE governance.source_registry SET status='failed', error=%s WHERE id=%s",
                    (str(exc), source_id),
                )
            conn.commit()
        raise HTTPException(status_code=500, detail=f"Failed to persist upload: {exc}") from exc

    return UploadResponse(
        source_id=source_id,
        original_filename=file.filename,
        storage_path=storage_path,
        size_bytes=len(content),
        row_count=profile.row_count,
        column_count=profile.column_count,
        suggested_table=suggested,
        columns=[ColumnPreview(**c.__dict__) for c in profile.columns],
    )


@router.get("/sources", response_model=SourceListResponse)
def list_sources(limit: int = 50) -> SourceListResponse:
    """Return recent uploads for the Data Health / Ingest dashboard."""
    limit = max(1, min(limit, 200))
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, uploaded_at, original_filename, size_bytes,
                           row_count, column_count, suggested_table, status, error
                    FROM governance.source_registry
                    ORDER BY uploaded_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
    except Exception:
        # Schema not applied yet → return an empty list rather than 500ing.
        # The migration target is documented in the README.
        return SourceListResponse(sources=[])

    return SourceListResponse(
        sources=[
            SourceListEntry(
                id=r["id"],
                uploaded_at=r["uploaded_at"].isoformat(),
                original_filename=r["original_filename"],
                size_bytes=r["size_bytes"],
                row_count=r["row_count"],
                column_count=r["column_count"],
                suggested_table=r["suggested_table"],
                status=r["status"],
                error=r["error"],
            )
            for r in rows
        ]
    )
