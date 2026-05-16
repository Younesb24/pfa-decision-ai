"use client";

import * as React from "react";
import {
  AlertTriangle,
  BarChart3,
  Brain,
  ChevronRight,
  Database,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wrench,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { EvidencePill } from "@/components/dashboard/evidence-pill";
import type { DecisionBrief, RecommendedAction } from "@/lib/types";
import { cn } from "@/lib/utils";

const API_BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1")
    : "http://localhost:8000/api/v1";

// ── Action dispatcher ──────────────────────────────────────────────────────────

async function fireAction(action: RecommendedAction): Promise<string> {
  try {
    if (action.action_type === "email") {
      const r = await fetch(`${API_BASE}/act/email/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_ref: (action.payload.subject_ref as string) ?? "agent_brief",
          target_role: (action.payload.target_role as string) ?? "seller",
          context: action.payload,
        }),
      });
      const j = await r.json();
      return j.detail ?? `Draft created (action ${j.action_id})`;
    }
    if (action.action_type === "webhook") {
      const r = await fetch(`${API_BASE}/act/webhook`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_ref: (action.payload.subject_ref as string) ?? "agent_brief",
          channel: (action.payload.channel as string) ?? "slack",
          title: action.label,
          body: (action.payload.body as string) ?? action.label,
          severity: action.urgency === "high" ? "critical" : "warning",
        }),
      });
      const j = await r.json();
      return j.detail ?? "Webhook fired";
    }
    if (action.action_type === "escalation") {
      const r = await fetch(`${API_BASE}/act/escalate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_ref: (action.payload.subject_ref as string) ?? "agent_brief",
          severity: action.urgency === "high" ? "critical" : "warning",
          reason: action.label,
        }),
      });
      const j = await r.json();
      return j.detail ?? "Escalated";
    }
    return "No action taken";
  } catch (e) {
    return `Error: ${String(e)}`;
  }
}

// ── Urgency badge ──────────────────────────────────────────────────────────────

const URGENCY_BADGE: Record<string, string> = {
  high:   "bg-rose-500/15 text-rose-400 ring-rose-500/30",
  medium: "bg-amber-500/15 text-amber-400 ring-amber-500/30",
  low:    "bg-sky-500/15   text-sky-400   ring-sky-500/30",
};

// ── Dynamic chart ──────────────────────────────────────────────────────────────

function DynamicChart({ brief }: { brief: DecisionBrief }) {
  const ch = brief.chart_hint;
  if (!ch || !ch.data.length) return null;

  const data = ch.data as Record<string, unknown>[];
  const ChartComponent = ch.chart_type === "bar" ? BarChart : AreaChart;
  const DataSeries = ch.chart_type === "bar" ? Bar : Area;

  return (
    <div className="mt-4 rounded-lg overflow-hidden border border-border/50 bg-[color:var(--surface-1)]">
      {ch.title && (
        <div className="px-4 py-2 text-[0.72rem] font-medium text-muted-foreground border-b border-border/50 flex items-center gap-1.5">
          <BarChart3 className="h-3.5 w-3.5" />
          {ch.title}
        </div>
      )}
      <div className="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <ChartComponent data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" strokeOpacity={0.4} />
            <XAxis
              dataKey={ch.x_key}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: unknown) => {
                const s = String(v);
                return s.length > 8 ? s.slice(5) : s; // trim YYYY- prefix
              }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                fontSize: "0.72rem",
              }}
            />
            {ch.chart_type === "bar" ? (
              <Bar
                dataKey={ch.y_key}
                fill="oklch(0.795 0.135 232)"
                radius={[3, 3, 0, 0]}
              />
            ) : (
              <Area
                dataKey={ch.y_key}
                stroke="oklch(0.795 0.135 232)"
                fill="oklch(0.795 0.135 232 / 0.15)"
                strokeWidth={1.5}
              />
            )}
          </ChartComponent>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ── Action button ──────────────────────────────────────────────────────────────

function ActionButton({ action }: { action: RecommendedAction }) {
  const [state, setState] = React.useState<"idle" | "loading" | "done" | "err">("idle");
  const [feedback, setFeedback] = React.useState<string>("");

  const handleClick = async () => {
    setState("loading");
    const msg = await fireAction(action);
    const hasError = msg.toLowerCase().startsWith("error");
    setState(hasError ? "err" : "done");
    setFeedback(msg);
  };

  const ActionIcon = {
    email: Zap,
    webhook: TrendingUp,
    escalation: AlertTriangle,
    review: Wrench,
  }[action.action_type] ?? Wrench;

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => void handleClick()}
        disabled={state === "loading" || state === "done"}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5",
          "text-[0.72rem] font-medium ring-1 ring-inset transition-all",
          state === "done"
            ? "bg-emerald-500/10 text-emerald-400 ring-emerald-500/30"
            : state === "err"
            ? "bg-rose-500/10 text-rose-400 ring-rose-500/30"
            : state === "loading"
            ? "opacity-60 cursor-not-allowed bg-[color:var(--surface-1)] text-muted-foreground ring-foreground/10"
            : "bg-[color:var(--surface-1)] text-foreground ring-foreground/10 hover:ring-primary/40 hover:bg-[color:var(--surface-2)]"
        )}
      >
        <ActionIcon className="h-3.5 w-3.5 shrink-0" />
        <span>{state === "loading" ? "…" : action.label}</span>
        <span
          className={cn(
            "ml-0.5 rounded px-1 py-0 text-[0.6rem] font-semibold uppercase tracking-wide",
            URGENCY_BADGE[action.urgency] ?? URGENCY_BADGE.medium,
            "ring-1 ring-inset"
          )}
        >
          {action.urgency}
        </span>
      </button>
      {feedback && (
        <p className={cn(
          "text-[0.65rem] pl-1",
          state === "err" ? "text-rose-400" : "text-emerald-400"
        )}>
          {feedback}
        </p>
      )}
    </div>
  );
}

// ── Section wrapper ────────────────────────────────────────────────────────────

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.10em] text-muted-foreground/80">
        <Icon className="h-3 w-3 shrink-0" strokeWidth={2.2} />
        {title}
      </div>
      {children}
    </div>
  );
}

// ── Main card ──────────────────────────────────────────────────────────────────

interface DecisionBriefCardProps {
  brief: DecisionBrief;
  onFollowUp?: (q: string) => void;
  className?: string;
}

export function DecisionBriefCard({ brief, onFollowUp, className }: DecisionBriefCardProps) {
  const isAbnormal =
    brief.is_it_abnormal.toLowerCase().includes("yes") ||
    brief.is_it_abnormal.toLowerCase().includes("abnormal") ||
    brief.is_it_abnormal.toLowerCase().includes("z-score") ||
    brief.is_it_abnormal.toLowerCase().includes("unusual");

  return (
    <div
      className={cn(
        "rounded-xl border border-border/60 bg-[color:var(--surface-1)]",
        "overflow-hidden divide-y divide-border/40",
        className
      )}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-start justify-between gap-3 bg-[color:var(--surface-2)]/50">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md ring-1 ring-inset ring-primary/30 bg-[color:var(--surface-2)]">
            <Brain className="h-3.5 w-3.5 text-primary" strokeWidth={2.2} />
          </div>
          <div className="min-w-0">
            <p className="text-[0.7rem] font-semibold text-muted-foreground uppercase tracking-[0.08em]">
              Decision Brief
            </p>
            <p className="text-[0.82rem] font-medium text-foreground truncate">
              {brief.question}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {brief.tool_calls_made.length > 0 && (
            <Badge
              variant="outline"
              className="text-[0.6rem] h-5 px-1.5 text-muted-foreground border-border/60"
            >
              <Database className="h-2.5 w-2.5 mr-1" />
              {brief.tool_calls_made.length} tool{brief.tool_calls_made.length !== 1 ? "s" : ""}
            </Badge>
          )}
          {brief.model && (
            <Badge
              variant="outline"
              className="text-[0.6rem] h-5 px-1.5 text-muted-foreground border-border/60"
            >
              {brief.provider}/{brief.model.split("-").slice(0, 2).join("-")}
            </Badge>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-5">
        {/* What happened */}
        <Section icon={Sparkles} title="What happened">
          <p className="text-[0.82rem] text-foreground/90 leading-relaxed">
            {brief.what_happened}
          </p>
        </Section>

        {/* Is it abnormal */}
        <Section icon={isAbnormal ? TrendingDown : TrendingUp} title="Abnormal?">
          <div className={cn(
            "rounded-md px-3 py-2 text-[0.78rem] leading-relaxed",
            isAbnormal
              ? "bg-amber-500/8 text-amber-300 ring-1 ring-inset ring-amber-500/20"
              : "bg-emerald-500/8 text-emerald-300 ring-1 ring-inset ring-emerald-500/20"
          )}>
            {brief.is_it_abnormal}
          </div>
        </Section>

        {/* Why it matters */}
        <Section icon={AlertTriangle} title="Why it matters">
          <p className="text-[0.82rem] text-foreground/90 leading-relaxed">
            {brief.why_it_matters}
          </p>
        </Section>

        {/* Evidence pills */}
        {brief.evidence.length > 0 && (
          <Section icon={Database} title="Evidence">
            <div className="flex flex-wrap gap-1.5">
              {brief.evidence.map((e, i) => (
                <EvidencePill key={i} evidence={e} />
              ))}
            </div>
          </Section>
        )}

        {/* Dynamic chart */}
        {brief.chart_hint && <DynamicChart brief={brief} />}

        {/* Recommended actions */}
        {brief.recommended_actions.length > 0 && (
          <Section icon={Zap} title="Recommended actions">
            <div className="flex flex-wrap gap-2">
              {brief.recommended_actions.map((a, i) => (
                <ActionButton key={i} action={a} />
              ))}
            </div>
          </Section>
        )}
      </div>

      {/* Follow-up chips */}
      {brief.follow_up_questions.length > 0 && (
        <div className="px-4 py-3 flex flex-wrap gap-1.5 bg-[color:var(--surface-2)]/30">
          <span className="text-[0.65rem] text-muted-foreground/60 self-center mr-1 uppercase tracking-[0.08em]">
            Follow up:
          </span>
          {brief.follow_up_questions.map((q, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onFollowUp?.(q)}
              className={cn(
                "inline-flex items-center gap-1 rounded-full",
                "px-2.5 py-0.5 text-[0.7rem] font-medium",
                "bg-[color:var(--surface-1)] text-muted-foreground",
                "ring-1 ring-inset ring-foreground/10",
                "hover:ring-primary/30 hover:text-foreground transition-colors"
              )}
            >
              {q}
              <ChevronRight className="h-2.5 w-2.5 opacity-50" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
