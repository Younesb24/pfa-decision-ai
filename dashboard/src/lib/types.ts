/* ─── Shared Types ─── */

export interface KPISummary {
  total_orders: number;
  total_revenue: number;
  avg_order_value: number;
  otif_rate: number;
  nps_proxy: number;
  cancellation_rate: number;
  active_sellers: number;
  unique_customers: number;
  period_start: string;
  period_end: string;
}

export interface DailyKPI {
  order_date: string;
  total_orders: number;
  total_gmv: number;
  aov: number;
  otif_rate: number | null;
  cancellation_rate: number;
  active_sellers: number;
}

export interface SellerScore {
  seller_id: string;
  total_orders: number;
  total_revenue: number;
  late_delivery_rate: number;
  avg_review_score: number;
  seller_risk_score: number;
}

export interface Forecast {
  orders: { month: string; value: number }[];
  revenue: { month: string; value: number }[];
  orders_mape: number;
  revenue_mape: number;
}

export interface AnomalyAlert {
  metric: string;
  date: string;
  value: number;
  z_score: number;
  direction: string;
  severity: string;
}

export interface AskResult {
  question: string;
  sql: string;
  data: Record<string, unknown>[] | null;
  error: string | null;
}
