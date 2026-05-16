# syntax=docker/dockerfile:1.6
#
# Dagster orchestration service.
#
# Two stages: builder resolves deps under /install; runtime is a slim image
# with the resolved site-packages + the dagster_pipeline package mounted at
# /app/dagster_pipeline. The container exposes the webserver UI on :3001 by
# default (override with $DAGSTER_PORT). Workers and the daemon are out of
# scope for this build — for the demo, the webserver is sufficient because
# we drive everything from the schedule / sensors UI.

# ─── builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY dagster_pipeline/requirements.txt .

RUN pip install --prefix=/install -r requirements.txt


# ─── runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    DAGSTER_PORT=3001

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10002 dagster && useradd --uid 10002 --gid dagster --shell /usr/sbin/nologin dagster

WORKDIR /app
COPY --from=builder /install /usr/local
# We import the pipeline as the module `dagster_pipeline`, so the source
# must live at /app/dagster_pipeline and /app must be on PYTHONPATH.
COPY --chown=dagster:dagster dagster_pipeline /app/dagster_pipeline

USER dagster
EXPOSE 3001

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:3001/server_info || exit 1

CMD ["dagster", "dev", "-m", "dagster_pipeline", "-p", "3001", "-h", "0.0.0.0"]
