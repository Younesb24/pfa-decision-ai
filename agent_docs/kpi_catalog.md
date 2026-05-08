# KPI Catalog — PFA Decision AI

## Source of truth for all KPIs. Read this before creating new metrics.

---

## 1. OTIF Rate (On-Time In-Full)

- **Definition**: Percentage of orders delivered on or before `estimated_delivery_date`
- **Formula**: `COUNT(orders WHERE NOT is_late AND status = 'delivered') / COUNT(orders WHERE status = 'delivered') * 100`
- **Target**: ≥ 92% (industry benchmark for e-commerce)
- **Grain**: daily / weekly / monthly
- **Source table**: `gold.fct_orders`
- **Alert threshold**: P1 if OTIF < 85%, P2 if < 90%

## 2. AOV (Average Order Value)

- **Definition**: Average revenue per order (price + freight)
- **Formula**: `SUM(total_order_value) / COUNT(DISTINCT order_id)`
- **Currency**: BRL (Brazilian Real)
- **Grain**: daily / weekly / monthly / by category / by region
- **Source table**: `gold.fct_orders`
- **Alert threshold**: P2 if AOV drops > 15% MoM

## 3. NPS Proxy (Net Promoter Score approximation)

- **Definition**: Proxy NPS from review scores (no actual survey data)
- **Formula**: `(% reviews score 4-5) - (% reviews score 1-2)`
- **Range**: -100 to +100
- **Grain**: monthly / by seller / by category
- **Source table**: `gold.fct_reviews`
- **Alert threshold**: P1 if NPS proxy < 0, P2 if < 30

## 4. Cancellation Rate

- **Definition**: Percentage of orders canceled vs total orders
- **Formula**: `COUNT(orders WHERE status = 'canceled') / COUNT(orders) * 100`
- **Grain**: daily / weekly / monthly
- **Source table**: `gold.fct_orders`
- **Alert threshold**: P2 if > 5%

## 5. Seller Risk Score (composite)

- **Definition**: Composite score to flag underperforming sellers
- **Components**:
  - Late delivery rate (weight: 40%)
  - Average review score (weight: 30%)
  - Volume stability — coefficient of variation of monthly orders (weight: 20%)
  - Cancellation rate (weight: 10%)
- **Formula**: Weighted average, normalized 0-100 (100 = highest risk)
- **Grain**: per seller, refreshed weekly
- **Source table**: `gold.agg_seller_scorecard`
- **Alert threshold**: P1 if score > 80, P2 if > 60

## 6. Revenue by Category

- **Definition**: Total revenue (price + freight) by product category
- **Grain**: daily / weekly / monthly
- **Source table**: `gold.fct_orders` joined with `gold.dim_product`

## 7. Delivery Delay Distribution

- **Definition**: Distribution of delivery_delay_days
- **Bins**: early (< -3 days), on-time (-3 to 0), slightly late (0-3), late (3-7), very late (> 7)
- **Source table**: `gold.fct_orders`
