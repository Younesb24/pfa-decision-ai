"use client";

import { ArrowDownRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";
import { Sparkline } from "./sparkline";
import { cn } from "@/lib/utils";

interface KpiTileProps {
  icon: LucideIcon;
  label: string;
  value: string;
  /** Sub-line under the label (e.g. "Target ≥ 92%"). */
  hint?: string;
  /** Trailing micro chart series (raw numbers). */
  trend?: number[];
  /** Hex color for the icon, sparkline, and accent (default: chart-1 sky). */
  accent?: string;
  /** Percent delta vs previous period — drives chip color & arrow. */
  delta?: number;
  /**
   * When `true`, the delta is suppressed and a "partial period" chip is shown
   * instead. Set by the page whenever the requested window extends past the
   * actual data cutoff (Olist historical case) — otherwise the trailing-window
   * delta looks like a recent collapse, which is the artifact we're fixing.
   */
  partial?: boolean;
  /** Apply success / warning / danger glow ring on hover. */
  tone?: "neutral" | "success" | "warning" | "danger";
  /** Animation delay class (e.g. animate-fade-up-2). */
  delay?: string;
}

const SKY = "oklch(0.795 0.135 232)";
const EMERALD = "oklch(0.785 0.155 162)";
const ROSE = "oklch(0.745 0.180 14)";
const AMBER = "oklch(0.835 0.165 80)";

function formatDelta(d: number): string {
  const abs = Math.abs(d);
  if (abs < 0.1) return "±0%";
  return `${d > 0 ? "+" : "−"}${abs.toFixed(1)}%`;
}

export function KpiTile({
  icon: Icon,
  label,
  value,
  hint,
  trend,
  accent = SKY,
  delta,
  partial = false,
  tone = "neutral",
  delay = "animate-fade-up-1",
}: KpiTileProps) {
  // When the requested window is partial (extends past data cutoff), suppress
  // the trailing-window delta — it would compare in-data days vs empty days
  // and looks like a -50% crash. The chip becomes a calm "partial" label
  // instead. This is the Day 1 KPI-delta-artifact fix.
  const showDelta = !partial && delta != null;

  const deltaTone =
    !showDelta
      ? "delta-flat"
      : delta! > 0.5
        ? "delta-up"
        : delta! < -0.5
          ? "delta-down"
          : "delta-flat";

  const DeltaIcon =
    !showDelta || Math.abs(delta!) < 0.5
      ? Minus
      : delta! > 0
        ? ArrowUpRight
        : ArrowDownRight;

  const toneClass =
    tone === "success"
      ? "hover:glow-success"
      : tone === "warning"
      ? "hover:glow-warning"
      : tone === "danger"
      ? "hover:glow-danger"
      : "";

  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-xl bg-card",
        "border border-border/60 px-5 pt-4 pb-3",
        "transition-all duration-200 top-highlight",
        "hover:border-border-strong hover:bg-[color:var(--surface-2)]",
        toneClass,
        delay
      )}
    >
      {/* Soft corner accent */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-12 -right-12 h-32 w-32 rounded-full opacity-[0.08] blur-2xl transition-opacity duration-300 group-hover:opacity-[0.18]"
        style={{ background: accent }}
      />

      {/* Header row */}
      <div className="flex items-center justify-between mb-4 relative">
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-md ring-1 ring-inset ring-foreground/10"
            style={{ background: `color-mix(in oklab, ${accent} 12%, transparent)` }}
          >
            <Icon className="h-3.5 w-3.5" style={{ color: accent }} strokeWidth={2.2} />
          </div>
          <span className="text-[0.68rem] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            {label}
          </span>
        </div>

        {partial ? (
          <span
            className="tabular inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wider text-[color:var(--warning)] bg-[color:var(--warning)]/10 ring-1 ring-inset ring-[color:var(--warning)]/30"
            title="Requested window extends past dataset cutoff — delta hidden"
          >
            partial period
          </span>
        ) : showDelta ? (
          <span
            className={cn(
              "tabular inline-flex items-center gap-0.5 text-[0.68rem] font-semibold",
              deltaTone
            )}
          >
            <DeltaIcon className="h-3 w-3" strokeWidth={2.5} />
            {formatDelta(delta!)}
          </span>
        ) : null}
      </div>

      {/* Value */}
      <div className="tabular text-3xl font-semibold tracking-tight text-foreground leading-none">
        {value}
      </div>

      {/* Hint */}
      {hint && (
        <div className="mt-1.5 text-[0.7rem] text-muted-foreground/80">
          {hint}
        </div>
      )}

      {/* Sparkline */}
      {trend && trend.length > 1 && (
        <div className="mt-3 -mx-1">
          <Sparkline data={trend} color={accent} height={32} />
        </div>
      )}
    </div>
  );
}

export const KPI_TONES = { SKY, EMERALD, ROSE, AMBER };
