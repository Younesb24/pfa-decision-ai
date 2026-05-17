# Demo script — 3-minute Loom (OTIF crisis)

> Target run-time: **3 min total**, ±15s. Recording cap: **2 takes**. If
> take 2 is still rough, ship it anyway — the deck (Day 20) carries the
> narrative weight, the Loom is just proof the thing breathes.

## Setup (do this once before hitting record)

- Stack is live on the public URL (AWS ALB DNS or Render — same script).
- Sign in once as `ops@pfa.local / ops123` so the bcrypt round-trip is
  warm and login is sub-second on camera.
- Open three browser tabs, **in this order, all the same browser window**:
  1. `<public-url>/` — dashboard with KPIs and the OTIF chart
  2. `<public-url>/data-health` — Connected Sources panel
  3. `<public-url>/docs` — FastAPI Swagger UI (proves the API surface
     exists; do **not** scroll it for more than 4s on camera)
- Browser zoom **125%**, dark mode (Shadcn looks better dark on Loom).
- Quit Slack, mute notifications, close DevTools.
- Have `scripts/replay_simulator.py --reset 2018-08-29` ready in a
  PowerShell tab in case the OTIF crisis day isn't in view. Don't record
  the reset — it's just for staging.

## Beats

### Beat 1 — Hook (0:00 – 0:15)

> "This is **PFA Decision AI** — a decision-support console for a
> Brazilian e-commerce marketplace. It answers one question for the
> Head of Ops every morning: *what should I do today and why.* The
> dataset is Olist — 100 000 real orders, 8 relational tables. Let me
> walk you through one bad day."

Land on **tab 1 (dashboard)**. No clicks yet. The hero KPIs are visible
behind your face cam.

### Beat 2 — Observe (0:15 – 0:55)

Click into the **OTIF chart**. Hover the dip on the synthetic-today
cursor.

> "OTIF — On-Time In-Full — sat above the 92% target for the previous
> two weeks. Yesterday it fell to **78%**. Below 85% the system flags
> a P1 alert. Here it is on the alert feed."

Scroll to **Anomaly alerts**. Read the alert headline aloud.

> "Z-score on the OTIF daily series triggered the alert. The threshold
> isn't tuned by the LLM — it's a deterministic z-score over the
> trailing 14 days. **Anomaly detection is code, not vibes.**"

### Beat 3 — Orient (0:55 – 1:40)

Click the alert. The narrative panel opens.

> "Now the LLM joins. Claude Sonnet takes the **pre-computed** KPIs and
> the top-N risky sellers — never the raw rows — and produces a
> persona-tailored briefing for the Head of Ops."

Read the first two sentences of the narrative aloud — even at 1.25×
playback, the viewer will hear the LLM grounded in real numbers.

> "Every number in this briefing came from `agg_daily_ops_kpi` and
> `agg_seller_scorecard` in our Gold layer. The LLM never sees Bronze.
> If you click 'show source', you get the SQL and the rows it ran on —
> this is the **audit trail**."

Click "show source" for 4 seconds. Don't dwell.

### Beat 4 — Decide (1:40 – 2:20)

Open the **risky sellers** table from the narrative.

> "The model named three sellers in the South region driving 60% of the
> late-delivery contribution. We have an XGBoost classifier
> predicting late-delivery probability per order; ROC-AUC ≈ 0.82 on
> the held-out window. The model card acknowledges the F1 is weak at
> 0.38 because the positive class is imbalanced — we'd ship a
> probability gauge, not a hard yes/no, in production."

Tab to **`/data-health`** for 3 seconds.

> "And here's why operations trusts the briefing: every Gold table
> shows freshness, row count, and the dbt test status. Nothing is
> served from a stale or test-failing source."

### Beat 5 — Act (2:20 – 2:50)

Back to **tab 1**. Find the alert. Click **Acknowledge / Mark as
reviewed**. Enter "Escalated to supply team — South cluster" in the
note.

> "The operator's decision lands in `governance.review_decisions`,
> linked back to the audit-log entry that produced this LLM output.
> Same shape as any modern decision-intelligence platform. **OODA loop
> in one tool.**"

Briefly flash **tab 3 (/docs)** showing `/governance/review` exists.

### Beat 6 — Sign-off (2:50 – 3:00)

Back to tab 1.

> "Stack is FastAPI, dbt, PostgreSQL, Next.js 14, Anthropic Claude,
> deployed on AWS Fargate. Source is at github.com/Younesb24/pfa-decision-ai.
> Thanks for watching."

Stop the recording.

## Lines NOT to say on camera

- "Claude wrote this." Never. The repo policy is documented in
  the handoff §0 and the auto-memory.
- "We use OpenAI as a fallback." True technically; off-message
  on a Loom whose hero is Anthropic.
- "It's pretty rough." It's three months of work. Don't apologize.
- Any model metric without context. "F1 of 0.38" alone sounds bad;
  "F1 0.38 on an imbalanced class, ROC-AUC 0.82, threshold tunable"
  is the same fact framed honestly.

## If something breaks on camera

- **Login 401:** re-seed users via `make seed-users`, re-record.
- **Narrative empty:** `ANTHROPIC_API_KEY` is not set on the live
  task — the template fallback still produces a paragraph, but it's
  obviously template. Skip the narrative beat and lean harder on the
  audit trail. The story still works.
- **No alerts visible:** `scripts/replay_simulator.py --reset 2018-08-29`
  in a separate terminal then refresh the dashboard. Stop the
  recording, do this, restart from Beat 1.

## Post-production

- Trim to **≤3:05** in Loom's editor.
- Title: **"PFA Decision AI — OTIF crisis walkthrough (3 min)"**.
- Thumbnail: the dashboard with the OTIF dip framed, your face in the
  corner.
- Privacy: **anyone with the link**. Do NOT password-gate — the jury
  shouldn't have to ask.
- Copy the share URL into `README.md` under the hero image (Day 18).
