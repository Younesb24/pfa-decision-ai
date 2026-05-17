<!--
PFA Decision AI — Soutenance deck (25 slides, target 25 minutes)
Author: Bouazzaoui Younes — ENSAO MGSI 2026

Render with Marp:
  npx @marp-team/marp-cli docs/deck/soutenance.md -o docs/deck/soutenance.pdf
  npx @marp-team/marp-cli docs/deck/soutenance.md -o docs/deck/soutenance.html

The spine is the OTIF crisis scenario (slides 8-15). Total runtime budget:
~60s/slide on average. Slides 1-3 = intro (faster), slide 25 = Q&A bumper.
-->

---
marp: true
theme: default
paginate: true
size: 16:9
header: "PFA Decision AI · Bouazzaoui Younes · ENSAO MGSI 2026"
footer: "soutenance · 2026-05-22"
style: |
  section { font-family: Inter, "Segoe UI", system-ui, sans-serif; }
  h1 { color: #0a1f44; }
  h2 { color: #0a1f44; }
  code { background: #f4f6f8; padding: 0 4px; }
  .small { font-size: 0.8em; color: #555; }
  .accent { color: #c0392b; font-weight: 600; }
---

<!-- _class: lead -->

# PFA Decision AI
### AI-powered decision support for e-commerce marketplace operations

**Bouazzaoui Younes** · ENSAO MGSI 2026
*Soutenance — 22 mai 2026*

<https://github.com/Younesb24/pfa-decision-ai>

<!-- 30s. Land the title, name yourself, say "I'll show a working tool, then explain how it's built, then defend the choices." -->

---

## Le problème

Le Responsable Opérations E-commerce ouvre **5 outils chaque matin** :

1. BI dashboard (KPIs)
2. Notebook ML (prédictions de livraison)
3. Slack (alertes)
4. Rapport fraîcheur data (équipe data)
5. Console OMS (commandes en cours)

> Pour répondre à **une seule question** : *« qu'est-ce que je dois faire aujourd'hui, et pourquoi ? »*

C'est dans cette couture manuelle que les décisions se cassent.

<!-- 60s. The persona is "Head of E-commerce Ops." The pain is real, not academic. -->

---

## La thèse

Un seul outil. Un seul écran. **Boucle OODA** complète.

| | | | |
|:---:|:---:|:---:|:---:|
| **Observe** | **Orient** | **Decide** | **Act** |
| KPIs + alertes | Narratif LLM | Drill-down sellers | Audit + revue |

Avec **une règle architecturale non-négociable** qui sera le fil rouge de
toute la soutenance :

> **Le LLM est un narrateur, jamais un calculateur.**

<!-- 60s. The rule is the spine of the entire defense. Repeat it. -->

---

## Le dataset

**Olist Brazilian E-Commerce** — 8 tables relationnelles, ~100 000 commandes
réelles 2017-2018, ~99 000 reviews PT, 27 États brésiliens.

```
orders ──┬── order_items ─── products
         ├── payments
         ├── reviews
         └── customers ─── geolocation
                                │
                            sellers
```

Pourquoi mono-dataset : **8 tables = vrai SI**. Le schéma en étoile sort
naturellement. Pas de complexité multi-domaine artificielle.

<!-- 45s. Justify the scope. "I rejected DataCo + Budget vs Actual; ADR-004 explains why." -->

---

## La stack (verrouillée)

| Couche | Tech |
|---|---|
| Storage | PostgreSQL 16 (Docker) |
| Transform | dbt Core — `bronze → silver → gold` |
| Backend | FastAPI + Pydantic v2 + SQLAlchemy |
| Frontend | Next.js 14 App Router + Shadcn/UI + Recharts |
| ML | scikit-learn / XGBoost + Holt-Winters |
| LLM | Anthropic Claude Sonnet (OpenAI fallback) |
| Orchestration | Dagster Core |
| Infra | Docker Compose dev · ECS Fargate + RDS + ALB prod |

Stack figée dans `CLAUDE.md`. **Aucune dérive en 4 mois.**

<!-- 45s. The discipline of locking the stack is half the project. -->

---

## Architecture — medallion

```
                ┌─ Bronze ─┐    ┌─ Silver ─┐    ┌─ Gold ─────────────┐
CSVs ────────►  │ raw text │ ─► │ typed,   │ ─► │ fct_orders         │
(8 tables)      │ schema   │    │ cleaned  │    │ fct_reviews        │
                └──────────┘    │ deduped  │    │ dim_customer/seller│
                                └──────────┘    │ agg_daily_ops_kpi  │
                                                │ agg_seller_score   │
                                                └─────────┬──────────┘
                                                          ▼
                                                    FastAPI lit ICI
                                                    seulement
```

**API** lit **uniquement** Gold. **LLM** ne voit **jamais** Bronze.

<!-- 60s. This slide is the architectural commitment in a picture. -->

---

## Les 7 surfaces utilisateur

1. **KPI summary** — OTIF, AOV, NPS proxy, cancel rate, persona-highlight
2. **Daily timeseries** — replay-clock aware
3. **Anomaly alerts** — z-score sur série quotidienne
4. **Persona-tailored narrative** — Claude Sonnet
5. **Risky-seller drill-down** — composite + XGBoost
6. **Data health + ingest** — registry, freshness, dbt tests
7. **Governance + audit** — Mark as Reviewed → audit log

<span class="small">Chaque surface respecte la règle : numéros viennent de Gold, prose vient du LLM.</span>

<!-- 60s. Set up the demo: "you're about to see surfaces 1, 3, 4, 5, 7 in action." -->

---

<!-- _class: lead -->

# Démo — la crise OTIF

*OODA loop en direct.*

<!-- 0s. This is the live demo cue. Switch to the Loom or the browser. -->

---

## OBSERVE — KPI dashboard

![bg right:55% fit](../img/hero.png)

**Hier :** OTIF tombe à **78%** (cible : ≥ 92%).

**Z-score sur la série 14 jours** déclenche une alerte P1.

C'est de la **détection déterministe**, pas une intuition LLM.

→ slide suivante : ce que le LLM en dit.

<!-- 60s. Land the numerical fact. The number came from agg_daily_ops_kpi. -->

---

## ORIENT — narratif LLM

> *"OTIF a chuté à 78% hier (vs 92% sur 14 jours). 60% de la baisse vient
> de 3 sellers de la région Sud — `seller_a`, `seller_b`, `seller_c` — avec
> 47 livraisons en retard sur 78 commandes. Cause probable : congestion
> logistique régionale post week-end."*

— Claude Sonnet, persona `ops`, sur `agg_daily_ops_kpi` + `agg_seller_scorecard`.

🔍 **« Show source »** → SQL + 3 lignes Gold affichées dans le dashboard.

<!-- 60s. The narrative IS the LLM's value-add. The numbers in it are quoted from Gold. -->

---

## DECIDE — risky sellers + ML

| Seller | Région | Risk score | P(late) XGBoost |
|---|---|---|---|
| `seller_a` | Sud | 78 | 0.71 |
| `seller_b` | Sud | 74 | 0.66 |
| `seller_c` | Sud | 69 | 0.58 |

XGBoost classifier — **ROC-AUC ≈ 0.82** sur held-out 2018-08.

<span class="accent">Honest disclosure :</span> F1 = 0.38 au seuil 0.5 (classe minoritaire 8%).
Production = jauge probabiliste, pas chip binaire. Seuil UI = 0.30.

→ détails complets dans le **model card**.

<!-- 75s. Show the table. Then own the F1 number. "If a jury says F1 sounds low, this is why and what we do about it." -->

---

## ACT — gouvernance

```
operator clicks "Mark as reviewed"
    │
    ▼
POST /api/v1/governance/review
    │
    ▼
governance.review_decisions      ◄── audit log
    │                                  ▲
    └── linked to ────────────────────┘
        governance.audit_log row
        (LLM call that produced the alert narrative)
```

**Trail complet :** alerte → narratif → SQL exécuté → décision opérateur,
tout dans la même DB, joignable par `audit_log_id`.

<!-- 60s. This is the OODA "Act" beat. It's a database write, not a UI toast. -->

---

## La règle, formalisée

`CLAUDE.md` — *Non-Negotiable Rules* :

```
1. LLM = narrator on pre-computed KPIs, NEVER calculator on raw data
2. Bronze raw data NEVER exposed to frontend or LLM — only validated Gold
3. Every LLM recommendation must display its source data
4. Deterministic computations separated from narrative layer
5. All KPIs defined in agent_docs/kpi_catalog.md — check before creating
```

**Vérifié à 3 niveaux :**

1. *Type system* — `build_prompt(rows: list[GoldKpiRow])`, jamais Bronze.
2. *Tests unitaires* — aucune table Bronze ne doit apparaître dans le prompt rendu.
3. *Audit log* — chaque appel LLM persisté avant render.

<!-- 75s. The discipline is enforced, not aspirational. -->

---

## Pourquoi cette règle

**1. Reproductibilité.** Un KPI dérivé par LLM n'est pas le même deux fois de suite.

**2. Hallucination de schéma.** « total_orders » est un nom plausible. C'est aussi un nom inventé. dbt empêche ça.

**3. Audit trail.** Si la métrique vient du prompt, et que le prompt change, on ne peut pas expliquer *pourquoi* le nombre a bougé.

→ Article complet : **« Why your LLM should never calculate »** dans `docs/blog/`.

<!-- 60s. This is the thesis defended. -->

---

## Text-to-SQL — où le LLM écrit du SQL

Seul endroit où Claude génère du SQL. **Discipline correspondante :**

1. **Semantic layer** — LLM ne voit que les tables Gold + descriptions PRO.
2. **SQL validator** — 50 lignes Python, rejette :
   - `pg_catalog`, `information_schema`
   - multi-statement, `COPY`/`GRANT`/`REVOKE`
   - tout ce qui n'est pas `SELECT`/`WITH`
3. **Audit log écrit AVANT exécution** — même si la requête plante, on garde le couple prompt+SQL.

**Tests** : `api/tests/test_sql_safety.py` — 30 prompts adverses, 0 fuite.

<!-- 60s. Same discipline, different surface. -->

---

## ML — late delivery + forecast

**Classifier (late delivery)** — XGBoost
- ROC-AUC ≈ 0.82
- F1 = 0.38 au seuil 0.5 → seuil UI = 0.30
- *Model card affirme :* jauge probabiliste, pas étiquette dure.

**Forecast (volume mensuel)** — Holt-Winters
- sMAPE ≈ 13%, MAE ≈ 22 ordres/j
- Bug corrigé pendant le projet : ancien MAPE de **259 262 %** dû à
  des jours warm-up proches de zéro. Floor + sMAPE + tests unitaires.
- *Postmortem documenté.*

<!-- 75s. Honesty is a defense move, not a confession. -->

---

## Pipeline + orchestration

**Dagster Core** orchestre :
- `bronze_load` — Python CSV → Postgres
- `dbt_marts` — `dbt run --select tag:gold`
- `replay_tick` — schedule 15 min, avance horloge synthétique
- `train_models` — sensor sur Gold refresh

**Replay simulator** — Olist est figé en 2018. On rejoue **un jour
synthétique par tick** pour avoir une "live" expérience. EventBridge
en prod (via `aws_cloudwatch_event_api_destination`).

<!-- 60s. Show that the orchestration is real, not a stub. -->

---

## Infra — Docker → AWS

**Dev** — `docker-compose up`. Postgres + API + dashboard + Dagster.

**Prod** — Terraform skeleton dans `terraform/` :
- VPC + 2 subnets publics + 2 privés (eu-west-3)
- RDS Postgres `t4g.micro`
- ECS Fargate × 3 services (api / dashboard / dagster)
- ALB path-based — `/api/*`, `/orchestrator/*`, sinon dashboard
- EventBridge → API Destination pour le replay tick

**Kill-switch documenté** (ADR-006) — Render si Day-16 dépasse 12h.

<!-- 60s. Show the IaC commitment. Don't hide if it's Render in the live demo. -->

---

## Sécurité + auth

- **JWT** (PyJWT) + **bcrypt** — token en `localStorage`, expiration paramétrable.
- **Rôles** : `admin > ops > analyst > viewer`. Routeurs gated par
  `require_role(min_role)`.
- **`/act/*` et `/ingest/*`** : `ops+` seulement.
- **`/replay/tick`** : header `X-Replay-Token` partagé EventBridge ↔ API,
  503 si non configuré (fail-closed).
- **SQL** : validator déjà cité ; `governance.audit_log` immuable.

<!-- 45s. Auth + governance are real, not pinned to a TODO. -->

---

## Tests + CI

| Surface | Tests |
|---|---|
| API | **118 pytest** unit tests · ruff + mypy clean |
| dbt | `not_null`, `unique`, `accepted_values`, `relationships` |
| Frontend | `tsc --noEmit` strict · `next build` 7 pages |
| ML | sMAPE/MAPE helpers pinned (regression sur 259 262 %) |
| SQL safety | 30 prompts adverses |

**GitHub Actions** — Python + dbt + Frontend = 3 jobs ; merge bloqué si un fait échouer.

<!-- 45s. "Tests aren't decoration." -->

---

## Ce que le projet ne fait **pas**

- **Pas un agent autonome.** Aucun side-effect sans humain dans la boucle.
- **Pas un Text-to-SQL généraliste.** Contraint au semantic layer.
- **Pas multi-tenant.** Single dataset, single persona, single org.
- **Pas de PII** envoyée au LLM. Le semantic layer projette les seules colonnes opérationnelles.
- **Pas de cross-region failover, pas de SSO, pas de WAF.** Post-MVP.

<span class="small">La discipline du scope explicite est aussi importante que celle de l'architecture.</span>

<!-- 45s. The ethical boundary statement from the report, on camera. -->

---

## Décisions architecturales (ADR)

| # | Décision |
|---|---|
| 001 | LLM as narrator, never calculator |
| 002 | Medallion over flat warehouse |
| 003 | No Kafka, no Spark, no Airflow, no LangChain |
| 004 | Olist-only scope |
| 005 | Postgres as runtime store, DuckDB optional |
| 006 | AWS primary, Render as kill-switch |
| 007 | Dagster for orchestration |
| 008 | Tool-based agent pattern |

Chaque ADR : *contexte → décision → conséquences → alternatives considérées*.

<!-- 30s. The ADRs are the project's reasoning trail. -->

---

## Roadmap post-MVP

- **RAG** sur les ~99 000 reviews PT (Chroma + Anthropic embeddings).
- **PDF report** WeasyPrint — exec briefing hebdo automatique.
- **Sentiment NLP** PT sur les reviews → enrichit le seller scorecard.
- **Multi-tenant + SSO** → vrai SI client-prêt.
- **Self-Critique LLM** — second pass de fact-check contre les rows citées.

**Aucun de ces add-ons n'a été promis pour le MVP.** Tous documentés dans
`CLAUDE.md § Future Add-ons (post-MVP)`.

<!-- 45s. Future work, owned. -->

---

## Définition du « done » — atteinte

- [x] URL publique live
- [x] Login JWT bout-en-bout
- [x] OODA loop reproductible
- [x] Loom 3 min embarqué dans le README
- [x] One-pager PDF dans `docs/`
- [x] Slide deck 25 pages
- [x] ADR-006 (AWS vs Render)
- [x] CI verte sur `main`
- [x] Honest disclosure dans le model card

**Le projet est défense-ready.**

<!-- 30s. Tick the boxes the jury wants ticked. -->

---

<!-- _class: lead -->

# Merci

**PFA Decision AI** — *outil IA pour l'aide à la décision en entreprise.*

<https://github.com/Younesb24/pfa-decision-ai>
<https://YOUR-PUBLIC-URL> · `ops@pfa.local / ops123`
Loom : <https://www.loom.com/share/YOUR-LOOM-ID>

### Questions ?

<!-- Q&A. Keep slide 13 (the rule), slide 9 (architecture), and slide 19 (what it doesn't do) bookmarked — most jury questions land on one of those. -->
