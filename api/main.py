"""
PFA Decision AI — FastAPI Backend
Serves KPIs, forecasts, anomalies, and LLM-powered insights
from the Gold layer of the Olist data warehouse.
"""

from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# pyrefly: ignore [missing-import]
from fastapi import FastAPI

# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # MUST be before router imports — they read env vars at module level

from routers import ask, governance, health, insights, kpi, ml  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("🚀 PFA Decision AI API starting...")
    yield
    print("👋 PFA Decision AI API shutting down...")


app = FastAPI(
    title="PFA Decision AI",
    description=(
        "API d'aide à la décision pour les opérations e-commerce marketplace. "
        "Transforme les données Olist en KPIs, alertes et recommandations narratives."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(health.router, tags=["Health"])
app.include_router(kpi.router, prefix="/api/v1", tags=["KPIs"])
app.include_router(ml.router, prefix="/api/v1", tags=["ML"])
app.include_router(ask.router, prefix="/api/v1", tags=["Text-to-SQL"])
app.include_router(insights.router, prefix="/api/v1", tags=["Insights"])
app.include_router(governance.router, prefix="/api/v1", tags=["Governance"])
