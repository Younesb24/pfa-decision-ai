"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  BookOpen,
  Brain,
  CircleDot,
  DollarSign,
  Layers,
  MessageSquare,
  ShoppingCart,
  Smile,
  Sparkles,
  Target,
  TrendingUp,
  Truck,
  Users,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Sidebar } from "@/components/dashboard/sidebar";
import { TopBar } from "@/components/dashboard/top-bar";
import { KpiTile, KPI_TONES } from "@/components/dashboard/kpi-tile";
import { Panel } from "@/components/dashboard/panel";
import { AnomalyCard } from "@/components/dashboard/anomaly-card";
import {
  askQuestion,
  fetchAlerts,
  fetchCategories,
  fetchDailyKpis,
  fetchForecast,
  fetchKpiSummary,
  fetchMlMetrics,
  fetchNarrative,
  fetchReplayState,
  fetchSellers,
} from "@/lib/api";
import { useTimeRange } from "@/lib/stores/useTimeRange";
import type {
  AnomalyAlert,
  AskResult,
  DailyKPI,
  Forecast,
  KPISummary,
  ReplayState,
  SellerScore,
} from "@/lib/types";
import { cn } from "@/lib/utils";

/* ─── Tokens ─── */
const C = {
  sky: KPI_TONES.SKY,        // chart-1
  emerald: KPI_TONES.EMERALD, // chart-2
  amber: KPI_TONES.AMBER,     // chart-3
  teal: "oklch(0.785 0.135 195)", // chart-4
  rose: KPI_TONES.ROSE,       // chart-5
};
const PIE_PALETTE = [C.sky, C.emerald, C.amber, C.teal, C.rose,
  "oklch(0.72 0.10 232)", "oklch(0.72 0.13 162)", "oklch(0.78 0.13 80)"];

/* ─── Format helpers ─── */
const fmt = (n: number) => new Intl.NumberFormat("en-US").format(Math.round(n));
const fmtK = (n: number) =>
  n >= 1_000_000
    ? `${(n / 1e6).toFixed(1)}M`
    : n >= 1_000
    ? `${(n / 1_000).toFixed(1)}k`
    : fmt(n);

/** Compact "Xm ago" / "Xh ago" formatter for the LIVE pill. Returns null
 *  when the input is missing so the caller can decide whether to render
 *  a fallback label. */
function formatRelativeSeconds(s: number | null | undefined): string | null {
  if (s == null || !Number.isFinite(s)) return null;
  if (s < 60) return `just now`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

/** Sub-line shown under a KPI tile label. Reflects the actively selected
 *  window when start/end are set, otherwise falls back to the dataset bounds
 *  echoed in the response. Day 1 — replaces the hardcoded "Last 90 days". */
function tileWindowHint(
  kpi: KPISummary,
  start: string | null,
  end: string | null,
): string {
  if (start && end) return `${start} → ${end}`;
  if (kpi.period_start && kpi.period_end) {
    return `${kpi.period_start} → ${kpi.period_end}`;
  }
  return "All data";
}

/** Compute % delta of the recent half vs the prior half of the series.
 *
 *  Adaptive window: previously hard-coded to 14d-vs-14d (needed >=28 rows),
 *  which silently produced no delta on shorter user-picked ranges. Now splits
 *  the supplied series in half so a 26-day range yields a 13d-vs-13d delta,
 *  a 7-day range yields a 3d-vs-3d delta, etc. Minimum of 2 points per half
 *  (4-point series) — below that, delta is genuinely meaningless. */
function computeDelta(series: number[]): number | undefined {
  if (!series || series.length < 4) return undefined;
  const half = Math.floor(series.length / 2);
  const recent = series.slice(-half);
  const prior = series.slice(-half * 2, -half);
  const avgRecent = recent.reduce((a, b) => a + b, 0) / recent.length;
  const avgPrior = prior.reduce((a, b) => a + b, 0) / prior.length;
  if (!avgPrior) return undefined;
  return ((avgRecent - avgPrior) / avgPrior) * 100;
}

export default function Dashboard() {
  const [kpi, setKpi] = useState<KPISummary | null>(null);
  const [daily, setDaily] = useState<DailyKPI[]>([]);
  const [sellers, setSellers] = useState<SellerScore[]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [categories, setCategories] = useState<Record<string, unknown>[]>([]);
  const [mlMetrics, setMlMetrics] = useState<Record<string, unknown> | null>(null);
  const [narrative, setNarrative] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<AnomalyAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [askInput, setAskInput] = useState("");
  const [askResult, setAskResult] = useState<AskResult | null>(null);
  const [askLoading, setAskLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "operations" | "logistics" | "sellers" | "forecast" | "alerts" | "ask" | "narratives" | "data" | "settings">("overview");
  const [replayState, setReplayState] = useState<ReplayState | null>(null);

  // Shared time range — drives /kpi/summary + /kpi/daily + /insights/*.
  const rangeStart = useTimeRange((s) => s.start);
  const rangeEnd = useTimeRange((s) => s.end);
  const setDataAsOf = useTimeRange((s) => s.setDataAsOf);

  // 1) Static fetches (no time-range dependency) — fired once.
  useEffect(() => {
    (async () => {
      try {
        const [s, f, c, m] = await Promise.all([
          fetchSellers(),
          fetchForecast(),
          fetchCategories(),
          fetchMlMetrics(),
        ]);
        setSellers(s);
        setForecast(f);
        setCategories(c);
        setMlMetrics(m);
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  // 2) Time-range-dependent fetches — re-fire when the picker changes.
  // The narrative + alerts now accept start/end (Day-2 follow-up), so the
  // briefing actually reflects the selected window instead of being a fixed
  // 27-month dump.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const range = { start: rangeStart, end: rangeEnd };
        const [k, d, a, n] = await Promise.all([
          fetchKpiSummary(range),
          fetchDailyKpis(range),
          fetchAlerts(range),
          fetchNarrative(range),
        ]);
        if (cancelled) return;
        setKpi(k);
        setDaily(d);
        setAlerts(a);
        setNarrative(n);
        // Seed the store's dataAsOf so the picker knows where Olist actually ends.
        if (k.data_as_of) setDataAsOf(k.data_as_of);
      } catch (e) {
        console.error(e);
      }
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [rangeStart, rangeEnd, setDataAsOf]);

  // 3) Replay-state poll — drives the LIVE pill. Fires once on mount then
  // every 60s. Failures are silent (the pill degrades to "idle"); we don't
  // want the dashboard to error just because Dagster paused.
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const s = await fetchReplayState();
      if (!cancelled) setReplayState(s);
    };
    void tick();
    const id = setInterval(() => void tick(), 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const handleAsk = async (override?: string) => {
    const q = (override ?? askInput).trim();
    if (!q) return;
    setAskLoading(true);
    setAskResult(null);
    const r = await askQuestion(q);
    setAskResult(r);
    setAskLoading(false);
    // Fix 2: clear the input after submission so the user sees an empty
    // search bar with the placeholder, not a stale value that reads as if it
    // were a hint.
    setAskInput("");
  };

  /** Fix 5: clicking a follow-up chip submits it as a new /ask query. */
  const handleFollowUp = (q: string) => {
    setAskInput(q);
    void handleAsk(q);
  };

  /* ─── Sidebar nav: update active state, then scroll/focus the right area. ─── */
  const NAV_TARGETS: Record<string, string | { focus: string }> = {
    overview: "page-top",
    operations: "kpis",
    logistics: "trend",
    sellers: "sellers",
    forecast: "forecast",
    alerts: "alerts",
    narratives: "briefing",
    ask: { focus: "ask-input" },
    data: { focus: "ask-input" },
    settings: "page-top",
  };

  const handleNavSelect = (id: string) => {
    setActiveTab(id as typeof activeTab);
    const target = NAV_TARGETS[id];
    if (!target) return;
    if (typeof target === "object" && "focus" in target) {
      const el = document.getElementById(target.focus) as HTMLElement | null;
      el?.focus();
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    if (target === "page-top") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    document
      .getElementById(target)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  /* ─── Derived series for sparklines & deltas ─── */
  const series = useMemo(() => {
    if (!daily || daily.length === 0) {
      return {
        orders: [], gmv: [], aov: [], otif: [], cancellation: [], sellers: [],
        deltaOrders: undefined as number | undefined,
        deltaGmv: undefined as number | undefined,
        deltaAov: undefined as number | undefined,
        deltaOtif: undefined as number | undefined,
        deltaCancel: undefined as number | undefined,
        deltaSellers: undefined as number | undefined,
      };
    }
    const orders = daily.map((d) => d.total_orders);
    const gmv = daily.map((d) => d.total_gmv);
    const aov = daily.map((d) => d.aov);
    const otif = daily.map((d) => d.otif_rate ?? 0);
    const cancellation = daily.map((d) => d.cancellation_rate);
    const sellers = daily.map((d) => d.active_sellers);
    return {
      orders, gmv, aov, otif, cancellation, sellers,
      deltaOrders: computeDelta(orders),
      deltaGmv: computeDelta(gmv),
      deltaAov: computeDelta(aov),
      deltaOtif: computeDelta(otif),
      deltaCancel: computeDelta(cancellation),
      deltaSellers: computeDelta(sellers),
    };
  }, [daily]);

  const ml = mlMetrics as Record<string, Record<string, number>> | null;

  /* ─── Loading screen ─── */
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="space-y-5 text-center">
          <div className="inline-flex items-center gap-2.5">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-lg ring-1 ring-inset ring-primary/30 bg-[color:var(--surface-2)] shadow-[0_0_28px_-6px_oklch(0.795_0.135_232/0.55)]">
              <Sparkles className="h-4 w-4 text-primary" strokeWidth={2.2} />
            </div>
            <div className="text-display text-2xl font-semibold tracking-tight text-brand-gradient">
              Olist Decision AI
            </div>
          </div>
          <div className="flex items-center justify-center gap-3">
            <Skeleton className="h-2 w-16" />
            <Skeleton className="h-2 w-24" />
            <Skeleton className="h-2 w-20" />
          </div>
          <p className="text-[0.7rem] uppercase tracking-[0.16em] text-muted-foreground/70">
            Loading marketplace intelligence…
          </p>
        </div>
      </div>
    );
  }

  /* ─── Status pills ─── */
  // Hide ROC-AUC / MAPE pills entirely when /ml/metrics returns empty
  // (no trained models yet). Showing "—" / "—%" looks like a broken UI;
  // omitting the pills makes the top bar honest.
  const rocAuc =
    ml && ml.late_delivery && typeof ml.late_delivery.roc_auc === "number"
      ? ml.late_delivery.roc_auc.toFixed(2)
      : null;
  const mape =
    ml && ml.forecast && typeof ml.forecast.mape === "number"
      ? `${ml.forecast.mape}%`
      : null;

  const statusPills = [
    rocAuc != null && { label: "ROC-AUC", value: rocAuc, tone: "info" as const },
    mape != null && { label: "MAPE", value: mape, tone: "info" as const },
    {
      label: "Anomalies",
      value: alerts.length.toString(),
      tone: alerts.some((a) => a.severity === "critical")
        ? ("danger" as const)
        : alerts.length > 0
        ? ("warning" as const)
        : ("success" as const),
    },
  ].filter(Boolean) as { label: string; value: string; tone: "info" | "success" | "warning" | "danger" }[];

  return (
    <div className="flex min-h-screen w-full bg-background">
      {/* Left rail */}
      <Sidebar active={activeTab} onSelect={handleNavSelect} />

      {/* Main column */}
      <main className="flex-1 min-w-0 px-4 lg:px-6 xl:px-8">
        {/* Sticky top bar */}
        <TopBar
          askValue={askInput}
          onAskChange={setAskInput}
          onAskSubmit={() => void handleAsk()}
          askLoading={askLoading}
          status={statusPills}
          period={
            kpi
              ? rangeStart && rangeEnd
                ? `${rangeStart} → ${rangeEnd}`
                : `${kpi.period_start} → ${kpi.period_end}`
              : undefined
          }
          live={
            replayState
              ? {
                  syntheticToday: replayState.synthetic_today,
                  lastRefreshLabel: formatRelativeSeconds(replayState.seconds_since_last_run),
                  initialised: replayState.initialised,
                }
              : { syntheticToday: null, lastRefreshLabel: null, initialised: false }
          }
        />

        {/* ───────── PAGE TITLE ───────── */}
        <div
          id="page-top"
          className="flex items-end justify-between flex-wrap gap-4 pt-6 pb-5 animate-fade-up scroll-mt-24"
        >
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 ring-1 ring-inset ring-primary/20 px-2 py-0.5 text-[0.6rem] font-semibold uppercase tracking-[0.12em] text-primary">
                <CircleDot className="h-2.5 w-2.5" strokeWidth={2.5} />
                Operations · Live
              </span>
              {kpi && (
                <span className="tabular text-[0.68rem] text-muted-foreground">
                  {fmt(kpi.active_sellers)} sellers · {fmt(kpi.unique_customers)} customers
                </span>
              )}
            </div>
            <h1 className="text-display text-3xl xl:text-4xl font-semibold tracking-tight">
              Marketplace Decision Cockpit
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground max-w-xl">
              AI decision support for the Head of E-commerce Ops — live
              replay-fed KPIs, z-score anomaly detection, persona-aware
              narratives, predictive late-delivery risk, Holt-Winters
              forecasting, and audited human review.
            </p>
          </div>
        </div>

        {/* ───────── ASK RESULT (conditional) ─────────
            Fix 1: structured Decision Brief-style render. Even on error or
            empty results, the user sees WHAT the AI tried (the SQL) and
            WHY it didn't work — never just a safety pill alone. */}
        {askResult && (
          <div className="mb-5 animate-fade-up">
            <Panel
              title={askResult.question}
              icon={<MessageSquare className="h-3.5 w-3.5 text-primary" strokeWidth={2.2} />}
              tag={
                <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[0.6rem] font-medium uppercase tracking-wider text-primary ring-1 ring-inset ring-primary/20">
                  Decision Analyst · Text-to-SQL
                </span>
              }
            >
              {/* Status line — sits above SQL so the operator sees outcome at a glance. */}
              <div className="mb-3 flex items-center flex-wrap gap-2 text-[0.7rem] tabular">
                {askResult.error ? (
                  <Badge variant="destructive" className="text-[0.65rem]">
                    {askResult.error}
                  </Badge>
                ) : askResult.data && askResult.data.length > 0 ? (
                  <span className="rounded-md bg-[color:var(--success)]/10 px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wider text-[color:var(--success)] ring-1 ring-inset ring-[color:var(--success)]/30">
                    {askResult.row_count ?? askResult.data.length} row{(askResult.row_count ?? askResult.data.length) === 1 ? "" : "s"}
                  </span>
                ) : (
                  <span className="rounded-md bg-[color:var(--warning)]/10 px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wider text-[color:var(--warning)] ring-1 ring-inset ring-[color:var(--warning)]/30">
                    No rows matched
                  </span>
                )}
                {askResult.model && (
                  <span className="text-muted-foreground/70">
                    via {askResult.provider}/{askResult.model}
                  </span>
                )}
              </div>

              {/* SQL — always shown when it exists, regardless of error/empty.
                  This is what the AI actually did; hiding it hides the AI. */}
              {askResult.sql ? (
                <pre className="font-mono text-[0.72rem] text-primary/85 surface-2 rounded-lg p-3.5 ring-1 ring-inset ring-foreground/10 overflow-auto mb-3 leading-relaxed whitespace-pre-wrap">
                  {askResult.sql}
                </pre>
              ) : (
                !askResult.error && (
                  <p className="text-[0.75rem] text-muted-foreground mb-3">
                    The model didn&apos;t emit any SQL. Try rephrasing your question.
                  </p>
                )
              )}

              {/* Data table */}
              {askResult.data && askResult.data.length > 0 && (
                <div className="overflow-auto max-h-72 rounded-lg ring-1 ring-inset ring-foreground/10 mb-3">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {Object.keys(askResult.data[0]).map((k) => (
                          <TableHead key={k} className="text-[0.65rem] uppercase tracking-wider">
                            {k}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {askResult.data.slice(0, 20).map((row, i) => (
                        <TableRow key={i} className="hover:bg-[color:var(--surface-2)]">
                          {Object.values(row).map((v, j) => (
                            <TableCell key={j} className="tabular text-xs">
                              {typeof v === "number" ? v.toLocaleString() : String(v)}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Fix 5: follow-up suggestion chips. Backend returns up to 3;
                  clicking one re-fires /ask with that question. */}
              {askResult.follow_up_questions && askResult.follow_up_questions.length > 0 && (
                <div className="border-t border-border/60 pt-3 mt-1">
                  <div className="text-[0.6rem] uppercase tracking-[0.1em] text-muted-foreground/70 mb-2">
                    Follow up
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {askResult.follow_up_questions.map((q, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => handleFollowUp(q)}
                        disabled={askLoading}
                        className={cn(
                          "tabular text-left rounded-md px-2.5 py-1 text-[0.7rem]",
                          "bg-[color:var(--surface-1)] hover:bg-[color:var(--surface-2)]",
                          "text-foreground ring-1 ring-inset ring-foreground/10",
                          "hover:ring-primary/40 transition-colors disabled:opacity-50"
                        )}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </Panel>
          </div>
        )}

        {/* ───────── KPI STRIP ───────── */}
        {kpi && (
          <section
            id="kpis"
            className="grid gap-3 grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 mb-5 scroll-mt-24"
          >
            <KpiTile
              icon={ShoppingCart}
              label="Total Orders"
              value={fmtK(kpi.total_orders)}
              hint={tileWindowHint(kpi, rangeStart, rangeEnd)}
              trend={series.orders}
              accent={C.sky}
              delta={series.deltaOrders}
              partial={kpi.is_partial_period}
              delay="animate-fade-up-1"
            />
            <KpiTile
              icon={DollarSign}
              label="Revenue (GMV)"
              value={`R$${fmtK(kpi.total_revenue)}`}
              hint="Gross merchandise value"
              trend={series.gmv}
              accent={C.emerald}
              delta={series.deltaGmv}
              partial={kpi.is_partial_period}
              tone="success"
              delay="animate-fade-up-2"
            />
            <KpiTile
              icon={BarChart3}
              label="Avg Order Value"
              value={`R$${kpi.avg_order_value.toFixed(0)}`}
              hint="KPI · operational"
              trend={series.aov}
              accent={C.teal}
              delta={series.deltaAov}
              partial={kpi.is_partial_period}
              delay="animate-fade-up-3"
            />
            <KpiTile
              icon={Truck}
              label="OTIF Rate"
              value={`${kpi.otif_rate.toFixed(1)}%`}
              hint="Target ≥ 92%"
              trend={series.otif}
              accent={kpi.otif_rate >= 92 ? C.emerald : C.amber}
              delta={series.deltaOtif}
              partial={kpi.is_partial_period}
              tone={kpi.otif_rate >= 92 ? "success" : "warning"}
              delay="animate-fade-up-4"
            />
            <KpiTile
              icon={Smile}
              label="NPS Proxy"
              value={`+${kpi.nps_proxy.toFixed(0)}`}
              hint="Review-derived score"
              accent={C.amber}
              partial={kpi.is_partial_period}
              delay="animate-fade-up-5"
            />
            <KpiTile
              icon={AlertTriangle}
              label="Cancel Rate"
              value={`${kpi.cancellation_rate.toFixed(2)}%`}
              hint="Alert > 5%"
              trend={series.cancellation}
              accent={kpi.cancellation_rate > 5 ? C.rose : C.emerald}
              delta={
                series.deltaCancel != null ? -series.deltaCancel : undefined
              }
              partial={kpi.is_partial_period}
              tone={kpi.cancellation_rate > 5 ? "danger" : "success"}
              delay="animate-fade-up-6"
            />
          </section>
        )}

        {/* ───────── NARRATIVE + ALERTS ───────── */}
        <div className="grid gap-3 grid-cols-1 lg:grid-cols-[2fr_1fr] mb-5">
          <Panel
            id="briefing"
            title="AI Executive Briefing"
            description="Automated weekly narrative on operational state"
            icon={<BookOpen className="h-3.5 w-3.5 text-primary" strokeWidth={2.2} />}
            tag={
              <span className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-1.5 py-0.5 text-[0.6rem] font-medium text-primary ring-1 ring-inset ring-primary/20">
                <Brain className="h-2.5 w-2.5" strokeWidth={2.5} />
                Sonnet 4.6
              </span>
            }
            delay="animate-fade-up-2"
          >
            {narrative ? (
              <NarrativeRenderer source={narrative} />
            ) : (
              <div className="space-y-2">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="h-3 w-4/5" />
              </div>
            )}
          </Panel>

          <Panel
            id="alerts"
            title="Anomaly Stream"
            description="Live z-score detection on KPI series"
            icon={<Bell className="h-3.5 w-3.5 text-amber-400" strokeWidth={2.2} />}
            tag={
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[0.6rem] font-medium ring-1 ring-inset",
                  alerts.some((a) => a.severity === "critical")
                    ? "bg-[color:var(--destructive)]/10 text-[color:var(--destructive)] ring-[color:var(--destructive)]/30"
                    : "bg-[color:var(--warning)]/10 text-[color:var(--warning)] ring-[color:var(--warning)]/30"
                )}
              >
                {alerts.length} detected
              </span>
            }
            contentClassName="px-2 py-2 max-h-[420px] overflow-y-auto"
            delay="animate-fade-up-3"
          >
            {alerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[color:var(--success)]/10 ring-1 ring-inset ring-[color:var(--success)]/30 mb-3">
                  <Target className="h-4 w-4 text-[color:var(--success)]" strokeWidth={2.2} />
                </div>
                <p className="text-sm font-medium text-foreground">All clear</p>
                <p className="text-[0.7rem] text-muted-foreground mt-0.5">
                  No anomalies in tracked KPIs
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-border/40">
                {alerts.slice(0, 12).map((a, i) => (
                  <AnomalyCard
                    key={`${a.metric}-${a.date}-${i}`}
                    alert={a}
                  />
                ))}
              </ul>
            )}
          </Panel>
        </div>

        {/* ───────── TREND + CATEGORY ───────── */}
        <div className="grid gap-3 grid-cols-1 lg:grid-cols-[2fr_1fr] mb-5">
          <Panel
            id="trend"
            title="GMV & Orders Trend"
            description="Last 90 days · daily aggregates"
            icon={<TrendingUp className="h-3.5 w-3.5 text-primary" strokeWidth={2.2} />}
            tag={
              <div className="flex items-center gap-3 text-[0.65rem]">
                <LegendDot color={C.emerald} label="GMV" />
                <LegendDot color={C.sky} label="Orders" />
              </div>
            }
            contentClassName="px-3 py-3"
            delay="animate-fade-up-3"
          >
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={daily} margin={{ top: 10, right: 8, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="gE" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.emerald} stopOpacity={0.32} />
                    <stop offset="95%" stopColor={C.emerald} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gB" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.sky} stopOpacity={0.22} />
                    <stop offset="95%" stopColor={C.sky} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke="oklch(0.965 0.005 240 / 0.05)" vertical={false} />
                <XAxis
                  dataKey="order_date"
                  tick={{ fill: "oklch(0.55 0.02 240)", fontSize: 10 }}
                  tickFormatter={(v) => v?.slice(5, 10)}
                  axisLine={false}
                  tickLine={false}
                  minTickGap={32}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fill: "oklch(0.55 0.02 240)", fontSize: 10 }}
                  tickFormatter={(v: number) => fmtK(v)}
                  axisLine={false}
                  tickLine={false}
                  width={48}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fill: "oklch(0.55 0.02 240)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  width={32}
                />
                <RTooltip
                  cursor={{ stroke: "oklch(0.965 0.005 240 / 0.10)", strokeWidth: 1 }}
                  formatter={(v, name) => {
                    const num = typeof v === "number" ? v : Number(v);
                    return [
                      name === "GMV (BRL)" ? `R$${fmt(num)}` : fmt(num),
                      String(name ?? ""),
                    ];
                  }}
                />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="total_gmv"
                  stroke={C.emerald}
                  strokeWidth={1.8}
                  fill="url(#gE)"
                  name="GMV (BRL)"
                />
                <Area
                  yAxisId="right"
                  type="monotone"
                  dataKey="total_orders"
                  stroke={C.sky}
                  strokeWidth={1.4}
                  fill="url(#gB)"
                  name="Orders"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Panel>

          <Panel
            title="Revenue by Category"
            description="Top 8 product verticals"
            icon={<Layers className="h-3.5 w-3.5 text-primary" strokeWidth={2.2} />}
            delay="animate-fade-up-4"
            contentClassName="px-3 py-3"
          >
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={categories.map((c) => ({
                    name: String(c.category || "").replace(/_/g, " "),
                    value: Number(c.total_revenue || 0),
                  }))}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={92}
                  innerRadius={52}
                  paddingAngle={2}
                  stroke="oklch(0.135 0.015 240)"
                  strokeWidth={2}
                  label={(props) => {
                    const p = (props as { percent?: number }).percent ?? 0;
                    return p > 0.06 ? `${(p * 100).toFixed(0)}%` : "";
                  }}
                  labelLine={false}
                >
                  {categories.map((_, i) => (
                    <Cell key={i} fill={PIE_PALETTE[i % PIE_PALETTE.length]} />
                  ))}
                </Pie>
                <RTooltip
                  formatter={(v, name) => [
                    `R$${fmt(typeof v === "number" ? v : Number(v))}`,
                    String(name ?? ""),
                  ]}
                />
                <Legend
                  layout="horizontal"
                  align="center"
                  verticalAlign="bottom"
                  iconType="circle"
                  iconSize={6}
                  wrapperStyle={{ fontSize: "0.62rem", paddingTop: 6 }}
                  formatter={(v: string) => (
                    <span className="text-muted-foreground">
                      {v.length > 14 ? v.slice(0, 14) + "…" : v}
                    </span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </Panel>
        </div>

        {/* ───────── FORECAST + SELLER RISK ───────── */}
        <div className="grid gap-3 grid-cols-1 lg:grid-cols-2 mb-5">
          {forecast && (
            <Panel
              id="forecast"
              title="3-Month Forecast"
              description="Holt-Winters exponential smoothing"
              icon={<TrendingUp className="h-3.5 w-3.5 text-primary" strokeWidth={2.2} />}
              tag={
                <span className="tabular inline-flex items-center gap-1 rounded-md bg-[color:var(--success)]/10 px-1.5 py-0.5 text-[0.6rem] font-medium text-[color:var(--success)] ring-1 ring-inset ring-[color:var(--success)]/30">
                  <Zap className="h-2.5 w-2.5" strokeWidth={2.5} />
                  MAPE {forecast.orders_mape}%
                </span>
              }
              delay="animate-fade-up-4"
              contentClassName="px-3 py-3"
            >
              <ResponsiveContainer width="100%" height={250}>
                <BarChart
                  data={forecast.orders.map((o, i) => ({
                    month: o.month,
                    orders: Math.round(o.value),
                    revenue: Math.round(forecast.revenue[i]?.value || 0),
                  }))}
                  margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
                >
                  <CartesianGrid strokeDasharray="2 4" stroke="oklch(0.965 0.005 240 / 0.05)" vertical={false} />
                  <XAxis
                    dataKey="month"
                    tick={{ fill: "oklch(0.55 0.02 240)", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fill: "oklch(0.55 0.02 240)", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fill: "oklch(0.55 0.02 240)", fontSize: 10 }}
                    tickFormatter={(v: number) => fmtK(v)}
                    axisLine={false}
                    tickLine={false}
                    width={48}
                  />
                  <RTooltip
                    cursor={{ fill: "oklch(0.965 0.005 240 / 0.05)" }}
                    formatter={(v) => fmt(typeof v === "number" ? v : Number(v))}
                  />
                  <Legend
                    iconType="circle"
                    iconSize={6}
                    wrapperStyle={{ fontSize: "0.65rem", paddingTop: 8 }}
                  />
                  <Bar
                    yAxisId="left"
                    dataKey="orders"
                    fill={C.sky}
                    radius={[4, 4, 0, 0]}
                    name="Orders"
                    barSize={28}
                  />
                  <Bar
                    yAxisId="right"
                    dataKey="revenue"
                    fill={C.emerald}
                    radius={[4, 4, 0, 0]}
                    name="Revenue (BRL)"
                    barSize={28}
                  />
                </BarChart>
              </ResponsiveContainer>
            </Panel>
          )}

          <Panel
            id="sellers"
            title="Seller Risk Scorecard"
            description="Highest delivery & rating risk"
            icon={<Users className="h-3.5 w-3.5 text-[color:var(--destructive)]" strokeWidth={2.2} />}
            tag={
              <span className="inline-flex items-center gap-1 rounded-md bg-[color:var(--warning)]/10 px-1.5 py-0.5 text-[0.6rem] font-medium text-[color:var(--warning)] ring-1 ring-inset ring-[color:var(--warning)]/30">
                Top 10
              </span>
            }
            delay="animate-fade-up-4"
            contentClassName="p-0"
          >
            <div className="overflow-x-auto max-h-[280px]">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent border-border/40">
                    <TableHead className="text-[0.6rem] uppercase tracking-[0.08em]">Seller</TableHead>
                    <TableHead className="text-[0.6rem] uppercase tracking-[0.08em] text-right">Orders</TableHead>
                    <TableHead className="text-[0.6rem] uppercase tracking-[0.08em] text-right">Late %</TableHead>
                    <TableHead className="text-[0.6rem] uppercase tracking-[0.08em] text-right">Rating</TableHead>
                    <TableHead className="text-[0.6rem] uppercase tracking-[0.08em]">Risk Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sellers.map((s) => (
                    <TableRow
                      key={s.seller_id}
                      className="hover:bg-[color:var(--surface-2)] border-border/40 transition-colors"
                    >
                      <TableCell className="font-mono text-[0.7rem] text-muted-foreground">
                        {s.seller_id.slice(0, 8)}…
                      </TableCell>
                      <TableCell className="tabular text-xs text-right">
                        {s.total_orders}
                      </TableCell>
                      <TableCell className="text-right">
                        <span
                          className={cn(
                            "tabular text-[0.72rem] font-medium",
                            s.late_delivery_rate > 20
                              ? "text-[color:var(--destructive)]"
                              : s.late_delivery_rate > 10
                              ? "text-[color:var(--warning)]"
                              : "text-foreground"
                          )}
                        >
                          {s.late_delivery_rate}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span
                          className={cn(
                            "tabular text-[0.72rem] font-medium",
                            s.avg_review_score < 3
                              ? "text-[color:var(--destructive)]"
                              : s.avg_review_score < 4
                              ? "text-[color:var(--warning)]"
                              : "text-[color:var(--success)]"
                          )}
                        >
                          {s.avg_review_score.toFixed(1)} ★
                        </span>
                      </TableCell>
                      <TableCell>
                        <RiskBar score={s.seller_risk_score} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Panel>
        </div>

        {/* ───────── FOOTER ───────── */}
        <footer className="flex flex-wrap items-center justify-between gap-3 py-5 mt-2 border-t border-border/60 text-[0.68rem] text-muted-foreground">
          <div className="flex items-center gap-2.5">
            <span className="pulse-dot relative inline-flex h-1.5 w-1.5 rounded-full text-[color:var(--success)] bg-[color:var(--success)]" />
            <span className="tabular">
              Olist Brazilian E-Commerce · {kpi?.period_start} → {kpi?.period_end}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span>PFA · MGSI ENSAO 2026</span>
            <span className="opacity-50">·</span>
            <span>Bronze → Silver → Gold</span>
            <span className="opacity-50">·</span>
            <span className="tabular">
              {fmt(kpi?.total_orders ?? 0)} orders indexed
            </span>
          </div>
        </footer>
      </main>
    </div>
  );
}

/* ─── Subcomponents ─── */

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: color }}
      />
      <span className="tabular text-[0.65rem] uppercase tracking-[0.06em]">
        {label}
      </span>
    </span>
  );
}

function RiskBar({ score }: { score: number }) {
  const color =
    score > 60 ? C.rose : score > 40 ? C.amber : C.emerald;
  return (
    <div className="flex items-center gap-2 min-w-[110px]">
      <div className="relative h-1 flex-1 rounded-full bg-[color:var(--surface-3)] overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
          style={{
            width: `${Math.min(100, score)}%`,
            background: color,
            boxShadow: `0 0 12px -2px ${color}`,
          }}
        />
      </div>
      <span
        className="tabular text-[0.7rem] font-semibold w-7 text-right"
        style={{ color }}
      >
        {score}
      </span>
    </div>
  );
}

function NarrativeRenderer({ source }: { source: string }) {
  return (
    <div className="text-[0.85rem] leading-relaxed text-muted-foreground space-y-1.5">
      {source.split("\n").map((line, i) => {
        if (line.startsWith("### ")) {
          return (
            <h4
              key={i}
              className="text-display text-foreground text-[0.78rem] font-semibold mt-4 mb-1.5 tracking-wide uppercase"
            >
              <span className="text-primary mr-2">▸</span>
              {line.replace("### ", "")}
            </h4>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h3
              key={i}
              className="text-display text-foreground text-sm font-semibold mt-4 mb-2"
            >
              {line.replace("## ", "")}
            </h3>
          );
        }
        if (line.startsWith("- ") || line.startsWith("* ")) {
          const txt = line.replace(/^[-*] /, "");
          const parts = txt.split(/\*\*(.*?)\*\*/);
          return (
            <div key={i} className="flex gap-2.5 ml-1">
              <span className="text-primary/80 shrink-0 mt-1">·</span>
              <span>
                {parts.map((p, j) =>
                  j % 2 === 1 ? (
                    <strong key={j} className="text-foreground font-semibold">
                      {p}
                    </strong>
                  ) : (
                    <span key={j}>{p}</span>
                  )
                )}
              </span>
            </div>
          );
        }
        if (line.match(/\*\*(.*?)\*\*/)) {
          const parts = line.split(/\*\*(.*?)\*\*/);
          return (
            <p key={i}>
              {parts.map((p, j) =>
                j % 2 === 1 ? (
                  <strong key={j} className="text-foreground font-semibold">
                    {p}
                  </strong>
                ) : (
                  <span key={j}>{p}</span>
                )
              )}
            </p>
          );
        }
        return line.trim() ? <p key={i}>{line}</p> : <div key={i} className="h-1.5" />;
      })}
    </div>
  );
}
