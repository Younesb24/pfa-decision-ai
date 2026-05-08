# Architecture — PFA Decision AI

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              Next.js 16 Dashboard (:3000)                     │ │
│  │  KPI Cards │ Area/Bar/Pie Charts │ Seller Table │ Ask Bar    │ │
│  │  AI Narrative │ Anomaly Alerts │ Forecast                    │ │
│  └────────────────────────┬─────────────────────────────────────┘ │
│                           │ HTTP/JSON                             │
│  ┌────────────────────────▼─────────────────────────────────────┐ │
│  │              FastAPI Backend (:8000)                           │ │
│  │  ┌─────────┐ ┌────────┐ ┌──────┐ ┌─────────┐ ┌───────────┐ │ │
│  │  │ /kpi/*  │ │ /ml/*  │ │ /ask │ │/insights│ │ /health   │ │ │
│  │  └─────────┘ └────────┘ └──────┘ └─────────┘ └───────────┘ │ │
│  └────────────────────────┬─────────────────────────────────────┘ │
│                           │                                       │
│           ┌───────────────┼───────────────┐                      │
│           │               │               │                      │
│  ┌────────▼──────┐ ┌──────▼─────┐ ┌──────▼──────────┐          │
│  │ PostgreSQL    │ │ ML Models  │ │ Anthropic Claude │          │
│  │ Gold Layer    │ │ (joblib)   │ │ (Text-to-SQL)    │          │
│  │ 9 tables      │ │ XGBoost    │ │ (Narratives)     │          │
│  │ 76 tests ✅   │ │ Holt-Win   │ │                  │          │
│  └───────────────┘ └────────────┘ └──────────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

## Medallion Architecture (dbt)

```
Bronze (9 raw CSVs)  →  Silver (9 clean views)  →  Gold (9 mart tables)
└── scripts/load_bronze.py  └── dbt_project/staging/  └── dbt_project/marts/
```

### Gold Star Schema

| Table | Type | Grain | Rows |
|-------|------|-------|------|
| dim_date | Dimension | 1 per day | 852 |
| dim_customer | Dimension | 1 per unique customer | 96,096 |
| dim_seller | Dimension | 1 per seller | 3,095 |
| dim_product | Dimension | 1 per product | 32,951 |
| dim_geo | Dimension | 1 per zip code | 27,911 |
| fct_orders | Fact | 1 per order item | 112,650 |
| fct_reviews | Fact | 1 per review | 99,224 |
| agg_daily_ops_kpi | Aggregate | 1 per day | 616 |
| agg_seller_scorecard | Aggregate | 1 per seller | 3,095 |

## API Endpoints (10)

| Endpoint | Purpose | Data Source |
|----------|---------|-------------|
| `/kpi/summary` | Global KPIs | agg_daily_ops_kpi |
| `/kpi/daily?days=N` | Daily timeseries | agg_daily_ops_kpi |
| `/kpi/sellers` | Seller risk scores | agg_seller_scorecard |
| `/kpi/revenue-by-category` | Category breakdown | fct_orders × dim_product |
| `/ml/metrics` | Model performance | joblib files |
| `/ml/forecast` | 3-month forecast | forecast_results.joblib |
| `/ask` | Text-to-SQL (Claude) | Any gold table |
| `/insights/narrative` | LLM executive summary | agg_daily_ops_kpi + scorecard |
| `/insights/alerts` | Z-score anomaly detection | agg_daily_ops_kpi |
| `/health` | Health check | - |

## ML Models

### Late Delivery Classifier
- **Algorithm:** XGBoost with scale_pos_weight
- **Features:** 34 (seller history, product, geography, time)
- **ROC-AUC:** 0.83 | **Threshold:** 0.645
- **Top feature:** seller_late_rate (from Gold agg)

### Sales Forecast
- **Algorithm:** Holt-Winters (statsmodels)
- **Seasonality:** 6-month (semi-annual)
- **MAPE:** 14% orders, 16% revenue

## Key Design Decisions

1. **LLM as narrator, not calculator** — All numbers come from dbt Gold layer (deterministic). Claude only interprets.
2. **Semantic layer as prompt** — Column descriptions from `_marts__models.yml` injected as system prompt → 75%+ SQL accuracy.
3. **Template fallback** — Narrative works without API key (important for soutenance).
4. **Z-score anomalies** — No ML needed for anomaly detection; pure SQL with statistical thresholds.
5. **Surrogate keys** — Star schema with integer keys for fast joins (not natural keys).
