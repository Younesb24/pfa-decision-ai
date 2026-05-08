# ADR 004 — Olist-only scope (cut DataCo + Budget vs Actual)

**Status:** Accepted
**Date:** 2026-04
**Related:** master plan §6 ("Datasets")

## Context

The original master plan combined three Kaggle datasets to claim a
multi-department surface (Supply Chain via DataCo, Sales/Ops via Olist,
Finance/CdG via Budget vs Actual). The implied story was *"a tool that handles
heterogeneous enterprise data."*

In practice, three datasets means three schemas, three ETL pipelines, three
documentation surfaces, and three sets of KPIs to specify — multiplied by one
solo developer on a four-month timeline.

## Decision

Ship Olist only. Cover the Operations persona end-to-end (ingestion → KPI →
narrative → alert → audit) before adding a second domain.

## Consequences

- **Honest framing:** the project description, README, and CV bullets now say
  "e-commerce marketplace operations," not "heterogeneous enterprise data."
  This survives a code-review interview.
- **Depth over breadth:** the demo can run end-to-end on a recruiter's laptop.
  The original 3-dataset plan would have shipped three half-pipelines.
- **Lost narrative:** the OODA-loop story across Supply + Finance + Sales is
  gone. We compensate by showing the loop end-to-end on the one domain we
  cover, which is more convincing than a partial story across three.

## Alternatives considered

- **Keep all three datasets, ship only the schemas.** Looks broad in the
  report, falls apart on demo day. Rejected.
- **Multi-persona view on one dataset.** Adopted as a partial recovery: the
  same Olist data is reframed for Ops / Supply / Finance via a `?persona=`
  query parameter (different KPI subsets and narrative tone). It restores the
  multi-department signal without a second pipeline. See `api/routers/kpi.py`.
- **Add a second dataset post-MVP.** Reasonable if the internship hunt allows;
  tracked in CLAUDE.md "Future Add-ons", not committed to a date.
