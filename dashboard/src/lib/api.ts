/* ─── API Service Layer ─── */
import type { KPISummary, DailyKPI, SellerScore, Forecast, AnomalyAlert, AskResult } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function fetchKpiSummary(): Promise<KPISummary> {
  const res = await fetchJson<{ data: KPISummary }>(`${API_BASE}/kpi/summary`);
  return res.data;
}

export async function fetchDailyKpis(days = 90): Promise<DailyKPI[]> {
  const res = await fetchJson<{ data: DailyKPI[] }>(`${API_BASE}/kpi/daily?days=${days}`);
  return (res.data || []).reverse();
}

export async function fetchSellers(limit = 10, minOrders = 30): Promise<SellerScore[]> {
  const res = await fetchJson<{ data: SellerScore[] }>(
    `${API_BASE}/kpi/sellers?limit=${limit}&min_orders=${minOrders}`
  );
  return res.data || [];
}

export async function fetchForecast(): Promise<Forecast | null> {
  const res = await fetchJson<{ data: Forecast }>(`${API_BASE}/ml/forecast`);
  return res.data || null;
}

export async function fetchCategories(topN = 8): Promise<Record<string, unknown>[]> {
  const res = await fetchJson<{ data: Record<string, unknown>[] }>(
    `${API_BASE}/kpi/revenue-by-category?top_n=${topN}`
  );
  return res.data || [];
}

export async function fetchMlMetrics(): Promise<Record<string, unknown> | null> {
  const res = await fetchJson<{ data: Record<string, unknown> }>(`${API_BASE}/ml/metrics`);
  return res.data || null;
}

export async function fetchNarrative(): Promise<string | null> {
  try {
    const res = await fetchJson<{ narrative: string }>(`${API_BASE}/insights/narrative`);
    return res.narrative;
  } catch {
    return null;
  }
}

export async function fetchAlerts(): Promise<AnomalyAlert[]> {
  try {
    const res = await fetchJson<{ alerts: AnomalyAlert[] }>(`${API_BASE}/insights/alerts`);
    return res.alerts || [];
  } catch {
    return [];
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
