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

/** Action Center (Day 5/6) — outbound actions fired against an anomaly. */
export type ActionType = "email" | "webhook" | "escalation";
export type ActionStatus = "drafted" | "sent" | "failed" | "cancelled";

export interface ActionResponse {
  action_id: number | null;
  status: ActionStatus | null;
  detail: string | null;
  generated_at: string;
}

export interface ActionHistoryEntry {
  id: number;
  created_at: string;
  action_type: string;   // permissive — older rows used legacy values
  channel: string;
  subject_ref: string;
  status: string;
  title: string | null;
  payload: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
}

/** Decision Analyst agent — structured brief (Day 7/8). */
export interface Evidence {
  metric: string;
  value: string | number;
  source: string;
  as_of?: string | null;
  unit?: string | null;
}

export interface ChartHint {
  chart_type: "bar" | "line" | "area";
  x_key: string;
  y_key: string;
  title?: string | null;
  data: Record<string, unknown>[];
}

export interface RecommendedAction {
  label: string;
  action_type: "email" | "webhook" | "escalation" | "review";
  urgency: "low" | "medium" | "high";
  payload: Record<string, unknown>;
}

export interface DecisionBrief {
  question: string;
  what_happened: string;
  is_it_abnormal: string;
  why_it_matters: string;
  evidence: Evidence[];
  chart_hint?: ChartHint | null;
  recommended_actions: RecommendedAction[];
  follow_up_questions: string[];
  tool_calls_made: string[];
  generated_at: string;
  provider?: string | null;
  model?: string | null;
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

/** Late delivery prediction — XGBoost classifier per seller. */
export interface FactorContribution {
  feature: string;
  label: string;
  value: number;
  contribution_pct: number;
  direction: "increases" | "decreases";
}

export interface LateDeliveryPrediction {
  seller_id: string;
  probability: number;
  threshold: number;
  predicted_late: boolean;
  /** Forward-looking: probability that a typical NEXT order is late. */
  risk_label: "low" | "medium" | "high";
  /** Backward-looking: derived from the scorecard composite. */
  historical_risk_label: "low" | "medium" | "high";
  seller_context: {
    state: string | null;
    total_orders: number;
    late_delivery_rate_pct: number;
    avg_review_score: number;
    seller_risk_score: number;
  };
  top_factors: FactorContribution[];
  recommendation: string;
  model: { name: string; n_features: number; threshold: number };
}
