"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle2,
  Clock,
  Database,
  RefreshCw,
  ServerCrash,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ReplayStatus {
  synthetic_today: string | null;
  last_run_at: string | null;
  age_seconds: number | null;
  initialised: boolean;
}

interface DbtStatus {
  last_test_pass_count: number;
  last_test_fail_count: number;
  last_test_warn_count: number;
  last_run_at: string | null;
  available: boolean;
}

interface ModelHealth {
  name: string;
  roc_auc?: number | null;
  mape?: number | null;
  drift_status: string;
  trained_at?: string | null;
}

interface AlertCount {
  kind: string;
  count: number;
}

interface DagsterStatus {
  reachable: boolean;
  last_24h_count: number;
  last_24h_success_rate: number;
}

interface DataHealth {
  checked_at: string;
  replay: ReplayStatus;
  dbt: DbtStatus;
  ml: ModelHealth[];
  alerts: AlertCount[];
  dagster: DagsterStatus;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function ageLabel(seconds: number | null): string {
  if (seconds == null) return "unknown";
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  return `${Math.round(seconds / 3600)}h ago`;
}

// ── Stat card ──────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  tone = "neutral",
  icon: Icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "neutral" | "ok" | "warn" | "error" | "offline";
  icon?: React.ComponentType<{ className?: string; strokeWidth?: number }>;
}) {
  const toneClass = {
    neutral: "ring-foreground/10 text-foreground",
    ok: "ring-emerald-500/30 text-emerald-400",
    warn: "ring-amber-500/30 text-amber-400",
    error: "ring-rose-500/30 text-rose-400",
    offline: "ring-border text-muted-foreground",
  }[tone];

  return (
    <div
      className={cn(
        "rounded-xl border bg-[color:var(--surface-1)] p-4 ring-1 ring-inset",
        toneClass
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        {Icon && <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />}
        <span className="text-[0.7rem] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold tabular-nums leading-tight">{value}</div>
      {sub && (
        <div className="mt-1 text-[0.68rem] text-muted-foreground/70">{sub}</div>
      )}
    </div>
  );
}

// ── Section header ─────────────────────────────────────────────────────────────

function SectionHeader({
  icon: Icon,
  title,
  badge,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  title: string;
  badge?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon className="h-4 w-4 text-primary" strokeWidth={2.2} />
      <h2 className="text-[0.88rem] font-semibold">{title}</h2>
      {badge}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function DataHealthPage() {
  const [health, setHealth] = useState<DataHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastPolled, setLastPolled] = useState<Date | null>(null);

  const fetchHealth = async () => {
    try {
      const { getToken } = await import("@/lib/auth");
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const r = await fetch(`${API_BASE}/data-health/status`, { headers });
      if (r.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login?next=/data-health";
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data: DataHealth = await r.json();
      setHealth(data);
      setLastPolled(new Date());
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchHealth();
    const id = setInterval(() => void fetchHealth(), 60_000);
    return () => clearInterval(id);
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-background px-6 py-8 max-w-5xl mx-auto">
        <div className="space-y-3">
          <Skeleton className="h-8 w-48" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        </div>
      </main>
    );
  }

  if (error && !health) {
    return (
      <main className="min-h-screen bg-background px-6 py-8 max-w-5xl mx-auto flex items-center justify-center">
        <div className="text-center space-y-2">
          <ServerCrash className="h-10 w-10 text-rose-400 mx-auto" />
          <p className="text-foreground font-medium">Data Health unavailable</p>
          <p className="text-muted-foreground text-sm">{error}</p>
          <button
            type="button"
            onClick={() => void fetchHealth()}
            className="mt-3 text-sm text-primary hover:underline"
          >
            Retry
          </button>
        </div>
      </main>
    );
  }

  if (!health) return null;

  const { replay, dbt, ml, alerts, dagster } = health;

  const replayAge = replay.age_seconds ?? null;
  const replayTone =
    !replay.initialised
      ? "offline"
      : replayAge == null
      ? "offline"
      : replayAge > 5400
      ? "error"
      : replayAge > 1800
      ? "warn"
      : "ok";

  const dbtTone = !dbt.available
    ? "offline"
    : dbt.last_test_fail_count > 0
    ? "error"
    : dbt.last_test_warn_count > 0
    ? "warn"
    : "ok";

  const dagsterTone = !dagster.reachable
    ? "offline"
    : dagster.last_24h_success_rate < 0.5
    ? "error"
    : dagster.last_24h_success_rate < 0.8
    ? "warn"
    : "ok";

  const totalAlerts = alerts.reduce((s, a) => s + a.count, 0);

  return (
    <main className="min-h-screen bg-background px-6 py-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Data Health</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Pipeline, models, and alert status — auto-refreshes every 60 s
          </p>
        </div>
        <div className="flex items-center gap-2">
          {lastPolled && (
            <span className="text-[0.68rem] text-muted-foreground">
              checked {lastPolled.toLocaleTimeString()}
            </span>
          )}
          <button
            type="button"
            onClick={() => void fetchHealth()}
            className="rounded-md p-1.5 hover:bg-[color:var(--surface-1)] text-muted-foreground hover:text-foreground transition-colors"
            title="Refresh now"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Overview row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
        <StatCard
          label="Replay"
          value={replay.synthetic_today ?? "—"}
          sub={ageLabel(replayAge)}
          tone={replayTone}
          icon={Clock}
        />
        <StatCard
          label="dbt Tests"
          value={dbt.available ? `${dbt.last_test_pass_count} / ${dbt.last_test_pass_count + dbt.last_test_fail_count}` : "—"}
          sub={dbt.available ? `${dbt.last_test_fail_count} failed` : "artifacts missing"}
          tone={dbtTone}
          icon={Database}
        />
        <StatCard
          label="Dagster"
          value={dagster.reachable ? `${Math.round(dagster.last_24h_success_rate * 100)}%` : "offline"}
          sub={dagster.reachable ? `${dagster.last_24h_count} runs in 24 h` : "unreachable"}
          tone={dagsterTone}
          icon={Activity}
        />
        <StatCard
          label="Open Alerts"
          value={totalAlerts}
          sub={totalAlerts === 0 ? "all clear" : `${alerts.length} kind${alerts.length !== 1 ? "s" : ""}`}
          tone={totalAlerts === 0 ? "ok" : totalAlerts > 5 ? "error" : "warn"}
          icon={AlertTriangle}
        />
      </div>

      {/* ML Models */}
      <section className="mb-10">
        <SectionHeader icon={Brain} title="ML Models" />
        {ml.length === 0 ? (
          <div className="rounded-xl border border-border/50 bg-[color:var(--surface-1)] p-6 text-center text-muted-foreground text-sm">
            No models trained yet. Run{" "}
            <code className="font-mono text-[0.78rem] bg-[color:var(--surface-2)] px-1 rounded">
              python ml/train_late_delivery.py
            </code>{" "}
            to train the late-delivery classifier.
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-4">
            {ml.map((m) => (
              <div
                key={m.name}
                className="rounded-xl border border-border/50 bg-[color:var(--surface-1)] p-4"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-medium text-sm">{m.name}</span>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-[0.6rem]",
                      m.drift_status === "ok"
                        ? "border-emerald-500/40 text-emerald-400"
                        : m.drift_status === "drift"
                        ? "border-amber-500/40 text-amber-400"
                        : "border-border/50 text-muted-foreground"
                    )}
                  >
                    {m.drift_status}
                  </Badge>
                </div>
                <div className="flex gap-6">
                  {m.roc_auc != null && (
                    <div>
                      <div className="text-[0.65rem] text-muted-foreground uppercase tracking-wide">
                        ROC-AUC
                      </div>
                      <div className="font-semibold tabular-nums">{m.roc_auc.toFixed(3)}</div>
                    </div>
                  )}
                  {m.mape != null && (
                    <div>
                      <div className="text-[0.65rem] text-muted-foreground uppercase tracking-wide">
                        MAPE
                      </div>
                      <div className="font-semibold tabular-nums">{m.mape.toFixed(1)}%</div>
                    </div>
                  )}
                </div>
                {m.trained_at && (
                  <div className="mt-2 text-[0.65rem] text-muted-foreground/60">
                    trained {m.trained_at.slice(0, 10)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* dbt test details */}
      <section className="mb-10">
        <SectionHeader
          icon={Database}
          title="dbt Test Results"
          badge={
            dbt.last_run_at ? (
              <span className="text-[0.65rem] text-muted-foreground">
                last run: {dbt.last_run_at.slice(0, 16).replace("T", " ")}
              </span>
            ) : null
          }
        />
        {!dbt.available ? (
          <div className="rounded-xl border border-border/50 bg-[color:var(--surface-1)] p-6 text-center text-muted-foreground text-sm">
            dbt artifacts not found. Run{" "}
            <code className="font-mono text-[0.78rem] bg-[color:var(--surface-2)] px-1 rounded">
              dbt test
            </code>{" "}
            from the <code className="font-mono text-[0.78rem]">dbt_project/</code> directory.
          </div>
        ) : (
          <div className="flex gap-4">
            <div className="flex items-center gap-2 rounded-lg bg-emerald-500/8 ring-1 ring-inset ring-emerald-500/20 px-4 py-2.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-semibold text-emerald-400">
                {dbt.last_test_pass_count} passed
              </span>
            </div>
            {dbt.last_test_fail_count > 0 && (
              <div className="flex items-center gap-2 rounded-lg bg-rose-500/8 ring-1 ring-inset ring-rose-500/20 px-4 py-2.5">
                <XCircle className="h-4 w-4 text-rose-400" />
                <span className="text-sm font-semibold text-rose-400">
                  {dbt.last_test_fail_count} failed
                </span>
              </div>
            )}
            {dbt.last_test_warn_count > 0 && (
              <div className="flex items-center gap-2 rounded-lg bg-amber-500/8 ring-1 ring-inset ring-amber-500/20 px-4 py-2.5">
                <AlertTriangle className="h-4 w-4 text-amber-400" />
                <span className="text-sm font-semibold text-amber-400">
                  {dbt.last_test_warn_count} warned
                </span>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Open Alerts */}
      {alerts.length > 0 && (
        <section className="mb-10">
          <SectionHeader icon={AlertTriangle} title="Open Governance Alerts" />
          <div className="rounded-xl border border-border/50 bg-[color:var(--surface-1)] overflow-hidden">
            {alerts.map((a, i) => (
              <div
                key={a.kind}
                className={cn(
                  "flex items-center justify-between px-4 py-3 text-sm",
                  i > 0 && "border-t border-border/40"
                )}
              >
                <span className="text-foreground font-mono text-[0.8rem]">{a.kind}</span>
                <Badge
                  variant="outline"
                  className="border-amber-500/40 text-amber-400 text-[0.65rem]"
                >
                  {a.count}
                </Badge>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Dagster */}
      <section>
        <SectionHeader icon={BarChart3} title="Dagster Orchestration" />
        {!dagster.reachable ? (
          <div className="rounded-xl border border-border/50 bg-[color:var(--surface-1)] p-6 text-center text-muted-foreground text-sm">
            Dagster offline — start with{" "}
            <code className="font-mono text-[0.78rem] bg-[color:var(--surface-2)] px-1 rounded">
              dagster dev -m dagster_pipeline -p 3001
            </code>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <StatCard
              label="Runs (24 h)"
              value={dagster.last_24h_count}
              tone="neutral"
            />
            <StatCard
              label="Success rate"
              value={`${Math.round(dagster.last_24h_success_rate * 100)}%`}
              tone={dagsterTone}
            />
          </div>
        )}
      </section>
    </main>
  );
}
