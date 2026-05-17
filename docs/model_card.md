# Model card — PFA Decision AI

> Honest disclosure of model performance, training scope, and known
> caveats for the two ML models in the system. Updated 2026-05-17 for
> the soutenance defense.

## 1. Late-delivery classifier

| Property | Value |
|---|---|
| Type | Binary classifier — `P(order delivered late)` |
| Algorithm | XGBoost (`xgboost.XGBClassifier`) |
| Training script | [ml/train_late_delivery.py](../ml/train_late_delivery.py) |
| Training data | Olist orders 2017-01-01 .. 2018-08-31, 80/20 split |
| Features | Order-level: payment type, seller risk score, freight cost, distance bucket, category, weekend flag |
| Artifact | `ml/models/late_delivery.joblib` + metrics JSON |

### Performance (most recent training run)

| Metric | Value | Comment |
|---|---|---|
| ROC-AUC (held-out) | ≈ **0.82** | Strong separation; the model ranks risk well |
| Accuracy | ≈ 0.91 | Misleading on its own — class imbalance |
| F1 at threshold 0.50 | **0.38** | Weak; many false negatives at the default cutoff |
| Precision | ≈ 0.55 | Tunable upward at the cost of recall |
| Recall | ≈ 0.29 | The headline weakness — half of late orders aren't flagged |

### Why F1 is low

The positive class — "late deliveries" — is ~8% of the dataset. At a
fixed 0.5 threshold the model under-predicts the minority class. Two
mitigations:

1. **Lower the threshold** (we use 0.30 in the UI's late-risk badge).
   At 0.30 the recall rises to ~0.55 and precision falls to ~0.40, which
   is the right trade-off for an *alerting* surface (false positives are
   cheap; missed alerts are expensive).
2. **Ship a probability gauge, not a hard label.** In the dashboard we
   render a gradient bar, not a yes/no chip. The operator interprets the
   number; the model never decides "this WILL be late."

### Disallowed uses

- **Do not** use this model to deny a seller payment automatically.
- **Do not** treat the probability as calibrated; we have not run
  isotonic regression / Platt scaling.
- **Do not** retrain on data outside `[2017-01-01, 2018-08-31]` — that is
  the full replay window of the Olist dataset, and any data outside it
  comes from upstream test corruption.

### Known caveats

- The Olist dataset is geographically biased to São Paulo / Rio. The
  model learns "distant zip code → high risk" which won't generalize
  to a global marketplace without retraining.
- We do **not** use the customer's review text as a feature. Reviews
  arrive *after* the late delivery; including them is leakage.

## 2. Order-volume forecast

| Property | Value |
|---|---|
| Type | Univariate time-series forecast (daily order count) |
| Algorithm | Holt-Winters (`statsmodels.tsa.holtwinters.ExponentialSmoothing`), additive trend, weekly seasonality |
| Training script | [ml/train_forecast.py](../ml/train_forecast.py) |
| Training data | Daily orders 2017-01-01 .. 2018-08-31 (Olist replay window) |
| Horizon | 90 days |
| Artifact | `ml/models/forecast.joblib` + metrics JSON |

### Performance (most recent training run)

| Metric | Value | Comment |
|---|---|---|
| MAPE (in-window holdout, last 30 days) | ~**14%** | Acceptable for a 90-day horizon on retail seasonality |
| MAE | ~22 orders/day | Useful for operational planning |
| sMAPE | ~13% | Robust to zero / near-zero days |

### The "MAPE = 259262%" caveat

A previous training run reported a MAPE of ~259 262 %. The bug was that
the eval window included **synthetic warm-up days** at the start of the
Olist series where the actual value was near zero — MAPE divides by the
actual, so even tiny absolute errors blow up. The fix in
`ml/train_forecast.py` is to restrict the eval window to
`[2017-04-01, 2018-08-15]` (post-warm-up, pre-window-edge) and to **also
report MAE and sMAPE** so a single garbage metric can't sink the report.
The current ~14% MAPE is honest.

### Disallowed uses

- **Do not** use this forecast to set inventory orders for an actual
  marketplace. The Olist dataset is a 2-year snapshot; the forecast has
  no concept of macro trends, marketing campaigns, or external shocks.
- **Do not** extend the forecast horizon beyond 90 days — uncertainty
  bands widen beyond the point of usefulness.

### Known caveats

- The model ignores promotions, holidays beyond the basic weekly cycle,
  and seller churn. A real production forecast would include exogenous
  regressors (Prophet-style) or be replaced with a learned model.
- Replay mode advances one synthetic day per 15-minute EventBridge tick,
  which means a "live" forecast at the dashboard is recomputed against
  shifting Bronze rows. The model itself does not retrain on replay
  ticks; only the input slice changes.

## 3. LLM components

These are not "models we trained" but they live in the same risk
surface, so they are documented here too.

| Component | Provider | Use |
|---|---|---|
| Text-to-SQL | Anthropic Claude Sonnet (OpenAI GPT-4o fallback) | Constrained NL → SQL over a semantic layer; queries are validated before execution |
| Narrative generation | Anthropic Claude Sonnet | Persona-tailored briefing on **pre-computed** KPIs and rows |
| Self-Critique | Anthropic Claude Sonnet | Second-pass fact-check against the rows the narrative cites |

### LLM governance

Every call writes a row to `governance.audit_log`:

```sql
audit_log(
  id,            -- uuid
  prompt_hash,   -- sha256 of the rendered prompt
  response,      -- raw model output
  sql_generated, -- if the call is text-to-SQL
  persona,       -- ops | finance | supply
  user_id,       -- the operator that triggered the call
  created_at     -- timestamptz
)
```

The operator can mark any output as reviewed via
`POST /governance/review`, which writes to `governance.review_decisions`
linked back to the audit row. This is the "Act" beat in the OODA loop —
auditable, reversible, attributed.

### Disallowed uses

- **The LLM never executes SQL it generated without a row in
  `audit_log`.** This is enforced at the router layer, not by convention.
- **The LLM never reads from `bronze.*`.** Every prompt template
  references only `gold.*` rows that have already passed dbt tests.
- **No customer PII (names, emails, full addresses) reaches the LLM.**
  The semantic layer projects only operational columns.

## 4. What we do not have (yet)

- **Calibration curves** for the late-delivery classifier. Worth adding
  post-defense before any "production" claim.
- **Concept-drift monitoring.** The Olist data is static, so drift is
  trivially zero. Real deployment would need a `pop_psi` job.
- **Adversarial / fairness eval on Brazilian regions.** Mentioned as
  future work in the slides.

---

*If you are reviewing this for a defense, the three honest answers are:*

1. *The ROC-AUC story is real. The F1 number is weak and we know why.*
2. *The forecast MAPE was a bug; the fix is in the script and the
   number you see on the dashboard now is the right one.*
3. *Every LLM output is traceable to a row in the audit log.*
