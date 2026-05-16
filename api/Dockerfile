# syntax=docker/dockerfile:1.6
#
# Multi-stage build for the FastAPI service.
#
# Stage `builder` resolves Python deps in an isolated layer so the runtime
# image doesn't carry pip / build wheels / system headers. Stage `runtime`
# only copies the resolved site-packages + application code, runs as an
# unprivileged user, and ships with curl for the HEALTHCHECK.

# ─── builder ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements.txt .

# psycopg2-binary ships wheels for slim so no compile step needed. bcrypt
# also ships wheels on python:3.12-slim — keep an eye on this if we bump
# Python or move to alpine (alpine needs build-base + libffi-dev for both).
RUN pip install --prefix=/install -r requirements.txt


# ─── runtime ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# curl is for the HEALTHCHECK below. Everything else stays out.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Non-root user — ECS / k8s will refuse images that run as uid 0 in many
# hardened configs, and the local risk is the same: a code-exec bug in a
# router shouldn't be able to chmod /etc.
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=app:app . /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
