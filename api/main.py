"""
PFA Decision AI — FastAPI Backend
Serves KPIs, forecasts, anomalies, and LLM-powered insights
from the Gold layer of the Olist data warehouse.
"""

from contextlib import asynccontextmanager
from pathlib import Path

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# pyrefly: ignore [missing-import]
from fastapi import FastAPI

# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

# Load .env from this file's directory (api/.env) regardless of cwd. The bare
# load_dotenv() walks up from cwd, which broke when uvicorn was launched from
# the project root via `--app-dir api` — POSTGRES_PASSWORD and ANTHROPIC_API_KEY
# would silently fall through to defaults. Anchoring to the module path keeps
# the API behaving the same whether you run `uvicorn main:app` from inside
# api/ or `uvicorn main:app --app-dir api` from the project root.
load_dotenv(Path(__file__).parent / ".env")  # MUST be before router imports
# Also try a project-root .env as a fallback (some operators prefer one file
# at the top level). load_dotenv with override=False is a no-op for vars that
# are already set.
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

from fastapi import Depends  # noqa: E402

from routers import (  # noqa: E402
    act,
    ask,
    auth,
    data_health,
    governance,
    health,
    ingest,
    insights,
    kpi,
    ml,
    replay,
)
from services.auth import require_role  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events.

    Avoid non-ASCII characters here — Python on Windows defaults to cp1252
    for stdout and chokes on emoji unless PYTHONIOENCODING/UTF8 are set.
    Boring prefixes work everywhere.
    """
    print("[startup] PFA Decision AI API starting...")
    yield
    print("[shutdown] PFA Decision AI API shutting down...")


app = FastAPI(
    title="PFA Decision AI",
    description=(
        "API d'aide à la décision pour les opérations e-commerce marketplace. "
        "Transforme les données Olist en KPIs, alertes et recommandations narratives."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend.
# Allow both `http://localhost:3000` AND `http://127.0.0.1:3000` — they're
# different *origins* to the browser even though they resolve to the same
# host. Without this, any browser tab opened on `127.0.0.1:3000` sees its
# fetches to `localhost:8000` get blocked, the dashboard's initial data
# load hangs on the loading screen, and you spend an evening debugging
# something that should have been a one-line config note.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1")
app.include_router(kpi.router, prefix="/api/v1", tags=["KPIs"])
app.include_router(ml.router, prefix="/api/v1", tags=["ML"])
app.include_router(ask.router, prefix="/api/v1", tags=["Text-to-SQL"])
app.include_router(insights.router, prefix="/api/v1", tags=["Insights"])
# Governance/Data Health: any signed-in analyst-or-above can read. Action
# Center is the only surface that touches outbound channels (email, webhooks,
# escalations) so it requires `ops` or `admin`. Auth is enforced at router
# level so a future route added under these prefixes inherits the guard by
# default — easier to remember than tagging every endpoint individually.
app.include_router(
    governance.router,
    prefix="/api/v1",
    tags=["Governance"],
    dependencies=[Depends(require_role("analyst"))],
)
app.include_router(replay.router, prefix="/api/v1", tags=["Replay"])
app.include_router(
    act.router,
    prefix="/api/v1",
    tags=["Act"],
    dependencies=[Depends(require_role("ops"))],
)
app.include_router(
    data_health.router,
    prefix="/api/v1",
    tags=["Data Health"],
    dependencies=[Depends(require_role("analyst"))],
)
app.include_router(
    ingest.router,
    prefix="/api/v1",
    tags=["Ingest"],
    dependencies=[Depends(require_role("ops"))],
)
