"use client";

import { Search, Sparkles, Activity, Command } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface StatusPill {
  label: string;
  value: string;
  tone?: "success" | "warning" | "danger" | "info";
}

interface TopBarProps {
  askValue: string;
  onAskChange: (v: string) => void;
  onAskSubmit: () => void;
  askLoading?: boolean;
  /** Right-side status pills. */
  status?: StatusPill[];
  /** Period text shown on the right (e.g. "Sep 4, 2018 → Aug 29, 2018"). */
  period?: string;
}

export function TopBar({
  askValue,
  onAskChange,
  onAskSubmit,
  askLoading,
  status = [],
  period,
}: TopBarProps) {
  return (
    <header
      className={cn(
        "sticky top-0 z-40 -mx-4 lg:-mx-6 xl:-mx-8 px-4 lg:px-6 xl:px-8 py-3",
        "border-b border-border/60 bg-background/80 backdrop-blur-xl"
      )}
    >
      <div className="flex items-center gap-3 lg:gap-4 min-w-0">
        {/* Live status indicator */}
        <div className="hidden sm:flex items-center gap-2 shrink-0">
          <span className="pulse-dot relative inline-flex h-1.5 w-1.5 rounded-full text-[color:var(--success)] bg-[color:var(--success)]" />
          <span className="tabular text-[0.68rem] uppercase tracking-[0.1em] text-muted-foreground hidden lg:inline">
            Live · Olist
          </span>
        </div>

        {/* Ask AI bar — center, wide */}
        <div
          className={cn(
            "relative flex-1 group flex items-center gap-2",
            "rounded-lg border border-border bg-[color:var(--surface-1)]",
            "px-3 py-1.5 transition-colors",
            "focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20"
          )}
        >
          <Search
            className="h-4 w-4 shrink-0 text-muted-foreground/70"
            strokeWidth={2}
            aria-hidden
          />
          <Input
            id="ask-input"
            value={askValue}
            onChange={(e) => onAskChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onAskSubmit()}
            placeholder="Ask anything in natural language — e.g. ‘Top 5 sellers by GMV in São Paulo’"
            className="h-7 border-0 bg-transparent px-0 text-sm placeholder:text-muted-foreground/60 focus-visible:ring-0 focus-visible:border-transparent"
            aria-label="Ask AI question"
          />
          <kbd className="hidden md:inline-flex tabular items-center gap-0.5 rounded px-1.5 py-0.5 text-[0.62rem] text-muted-foreground/70 bg-[color:var(--surface-2)] ring-1 ring-inset ring-foreground/10">
            <Command className="h-2.5 w-2.5" strokeWidth={2.5} />K
          </kbd>
          <Button
            type="button"
            size="sm"
            onClick={onAskSubmit}
            disabled={askLoading || !askValue.trim()}
            className="h-7 gap-1.5 px-3 font-medium shadow-sm shadow-primary/20"
          >
            <Sparkles className="h-3 w-3" strokeWidth={2.5} />
            {askLoading ? "Thinking…" : "Ask AI"}
          </Button>
        </div>

        {/* Status pills */}
        <div className="hidden lg:flex items-center gap-1.5 shrink-0">
          {status.map((s) => (
            <StatusPillView key={s.label} pill={s} />
          ))}
        </div>

        {period && (
          <div className="hidden xl:flex items-center gap-1.5 pl-3 border-l border-border/60 shrink-0">
            <Activity className="h-3 w-3 text-muted-foreground/60" strokeWidth={2} />
            <span className="tabular text-[0.7rem] text-muted-foreground/80">
              {period}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}

function StatusPillView({ pill }: { pill: StatusPill }) {
  const tone = pill.tone ?? "info";
  const colorClass =
    tone === "success"
      ? "text-[color:var(--success)]"
      : tone === "warning"
      ? "text-[color:var(--warning)]"
      : tone === "danger"
      ? "text-[color:var(--destructive)]"
      : "text-primary";

  return (
    <div
      className={cn(
        "tabular flex items-center gap-1.5 rounded-md",
        "px-2 py-1 text-[0.68rem] font-medium",
        "bg-[color:var(--surface-1)] ring-1 ring-inset ring-foreground/10"
      )}
    >
      <span className="text-muted-foreground/70 uppercase tracking-[0.06em]">
        {pill.label}
      </span>
      <span className={cn("font-semibold", colorClass)}>{pill.value}</span>
    </div>
  );
}
