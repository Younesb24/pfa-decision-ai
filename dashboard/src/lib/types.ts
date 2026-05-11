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
  /** max(order_date) on gold.agg_daily_ops_kpi — actual data cutoff. */
  data_as_of?: string | null;
  /** Echoed ?start= (null if not sent). */
  requested_start?: string | null;
  /** Echoed ?end= (null if not sent). */
  requested_end?: string | null;
  /** true when the requested window extends past data_as_of. */
  is_partial_period?: boolean;
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
  row_count?: number | null;
  provider?: string | null;
  model?: string | null;
  follow_up_questions?: string[];
}

/** Replay-simulator state — drives the dashboard's LIVE pill. */
export interface ReplayState {
  synthetic_today: string | null;
  runs_completed: number;
  last_run_at: string | null;
  last_run_status: string | null;
  last_run_rows: number | null;
  seconds_since_last_run: number | null;
  initialised: boolean;
}

/** Governance — human review decisions on AI surfaces. */
export type ReviewDecision = "acknowledge" | "dismiss" | "escalate";

export interface ReviewResult {
  recorded: boolean;
  review_id: number | null;
  generated_at: string;
}
