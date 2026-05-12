/* ─── API Service Layer ─── */
import type {
  ActionHistoryEntry,
  ActionResponse,
  AnomalyAlert,
  AskResult,
  DailyKPI,
  Forecast,
  KPISummary,
  ReplayState,
  ReviewDecision,
  ReviewResult,
  SellerScore,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/** A start/end pair accepted by every /kpi/* endpoint. Both nullable so
 *  callers can pass through the zustand store as-is. */
export interface DateRange {
  start: string | null;
  end: string | null;
}

function rangeQS(r?: DateRange): string {
  if (!r) return "";
  const qs: string[] = [];
  if (r.start) qs.push(`start=${r.start}`);
  if (r.end) qs.push(`end=${r.end}`);
  return qs.length ? qs.join("&") : "";
}

function joinQS(base: string, ...parts: string[]): string {
  const filled = parts.filter(Boolean);
  return filled.length ? `${base}?${filled.join("&")}` : base;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function fetchKpiSummary(range?: DateRange): Promise<KPISummary> {
  const url = joinQS(`${API_BASE}/kpi/summary`, rangeQS(range));
  const res = await fetchJson<{ data: KPISummary }>(url);
  return res.data;
}

export async function fetchDailyKpis(
  rangeOrDays: DateRange | number = 90,
): Promise<DailyKPI[]> {
  let url: string;
  if (typeof rangeOrDays === "number") {
    url = `${API_BASE}/kpi/daily?days=${rangeOrDays}`;
  } else {
    url = joinQS(`${API_BASE}/kpi/daily`, rangeQS(rangeOrDays));
  }
  const res = await fetchJson<{ data: DailyKPI[] }>(url);
  // Backend now returns ascending order; preserve compatibility if any path
  // ever flips this.
  const rows = res.data || [];
  return rows;
}

export async function fetchSellers(limit = 10, minOrders = 30): Promise<SellerScore[]> {
  const res = await fetchJson<{ data: SellerScore[] }>(
    `${API_BASE}/kpi/sellers?limit=${limit}&min_orders=${minOrders}`,
  );
  return res.data || [];
}

export async function fetchForecast(): Promise<Forecast | null> {
  const res = await fetchJson<{ data: Forecast }>(`${API_BASE}/ml/forecast`);
  return res.data || null;
}

export async function fetchCategories(topN = 8): Promise<Record<string, unknown>[]> {
  const res = await fetchJson<{ data: Record<string, unknown>[] }>(
    `${API_BASE}/kpi/revenue-by-category?top_n=${topN}`,
  );
  return res.data || [];
}

export async function fetchMlMetrics(): Promise<Record<string, unknown> | null> {
  const res = await fetchJson<{ data: Record<string, unknown> }>(`${API_BASE}/ml/metrics`);
  return res.data || null;
}

export async function fetchNarrative(range?: DateRange, persona = "ops"): Promise<string | null> {
  try {
    const qs = ["persona=" + persona, rangeQS(range)].filter(Boolean).join("&");
    const url = qs ? `${API_BASE}/insights/narrative?${qs}` : `${API_BASE}/insights/narrative`;
    const res = await fetchJson<{ narrative: string }>(url);
    return res.narrative;
  } catch {
    return null;
  }
}

export async function fetchAlerts(range?: DateRange): Promise<AnomalyAlert[]> {
  try {
    const url = joinQS(`${API_BASE}/insights/alerts`, rangeQS(range));
    const res = await fetchJson<{ alerts: AnomalyAlert[] }>(url);
    return res.alerts || [];
  } catch {
    return [];
  }
}

/** Replay-simulator state — drives the LIVE pill (synthetic_today + last refresh). */
export async function fetchReplayState(): Promise<ReplayState | null> {
  try {
    const res = await fetchJson<{ data: ReplayState }>(`${API_BASE}/replay/state`);
    return res.data;
  } catch {
    return null;
  }
}

// ── Action Center (Day 5/6) ────────────────────────────────────────────

/** GET /governance/actions — recent outbound actions for the history panel. */
export async function fetchActions(subjectRef?: string): Promise<ActionHistoryEntry[]> {
  try {
    const qs = subjectRef ? `?subject_ref=${encodeURIComponent(subjectRef)}` : "";
    const res = await fetchJson<{ entries: ActionHistoryEntry[] }>(
      `${API_BASE}/governance/actions${qs}`,
    );
    return res.entries || [];
  } catch {
    return [];
  }
}

/** POST /act/email/draft — LLM-drafted email scoped to the subject_ref. */
export async function draftActionEmail(input: {
  subject_ref: string;
  target_role?: "seller" | "internal_ops" | "carrier" | "category_manager";
  context?: Record<string, unknown>;
  recipient?: string;
}): Promise<ActionResponse | null> {
  try {
    return await fetchJson<ActionResponse>(`${API_BASE}/act/email/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject_ref: input.subject_ref,
        target_role: input.target_role ?? "seller",
        context: input.context ?? {},
        recipient: input.recipient ?? null,
      }),
    });
  } catch {
    return null;
  }
}

/** POST /act/email/send — flip a draft to sent (SMTP optional). */
export async function sendActionEmail(input: {
  action_id: number;
  body?: string;
  recipient?: string;
}): Promise<ActionResponse | null> {
  try {
    return await fetchJson<ActionResponse>(`${API_BASE}/act/email/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    return null;
  }
}

/** POST /act/webhook — fire a configured Slack/Linear/Jira webhook. */
export async function fireActionWebhook(input: {
  subject_ref: string;
  channel?: "slack" | "linear" | "jira";
  title: string;
  body: string;
  severity?: "info" | "warning" | "critical";
}): Promise<ActionResponse | null> {
  try {
    return await fetchJson<ActionResponse>(`${API_BASE}/act/webhook`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        channel: input.channel ?? "slack",
        severity: input.severity ?? "warning",
        ...input,
      }),
    });
  } catch {
    return null;
  }
}

/** POST /act/escalate — write a critical row to governance.alerts. */
export async function escalateAction(input: {
  subject_ref: string;
  severity?: "warning" | "critical";
  reason: string;
}): Promise<ActionResponse | null> {
  try {
    return await fetchJson<ActionResponse>(`${API_BASE}/act/escalate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ severity: "critical", ...input }),
    });
  } catch {
    return null;
  }
}

export async function askQuestion(question: string): Promise<AskResult> {
  try {
    return await fetchJson<AskResult>(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    return { question, sql: "", data: null, error: "API unreachable" };
  }
}

/** Mark an anomaly/alert as reviewed (Day 1 deliverable — closes OODA "Act"). */
export async function submitReview(input: {
  subject_ref: string;
  decision: ReviewDecision;
  note?: string;
  reviewer?: string;
}): Promise<ReviewResult> {
  try {
    return await fetchJson<ReviewResult>(`${API_BASE}/governance/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject_type: "alert",
        subject_ref: input.subject_ref,
        decision: input.decision,
        note: input.note ?? null,
        reviewer: input.reviewer ?? null,
      }),
    });
  } catch {
    return {
      recorded: false,
      review_id: null,
      generated_at: new Date().toISOString(),
    };
  }
}
