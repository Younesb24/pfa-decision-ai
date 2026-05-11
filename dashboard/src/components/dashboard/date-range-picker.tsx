"use client";

/**
 * DateRangePicker — header control for the dashboard window.
 *
 * Day 1 deliverable. Renders a calendar-icon button in the TopBar that opens
 * a small panel with:
 *   - preset chips (7 / 30 / 90 / 365 days, All)
 *   - two ISO date inputs for a custom range
 *   - a "partial period" badge when the chosen window ends past data_as_of
 *
 * State lives in the shared `useTimeRange` zustand store so every fetcher
 * reads from a single source of truth.
 */

import { useEffect, useRef, useState } from "react";
import { CalendarRange, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  type RangePreset,
  isPartialPeriod,
  useTimeRange,
} from "@/lib/stores/useTimeRange";
import { cn } from "@/lib/utils";

const PRESETS: { id: RangePreset; label: string }[] = [
  { id: "7d", label: "7d" },
  { id: "30d", label: "30d" },
  { id: "90d", label: "90d" },
  { id: "365d", label: "1y" },
  { id: "all", label: "All" },
];

function formatRange(start: string | null, end: string | null): string {
  if (!start && !end) return "All data";
  if (start && end) return `${start} → ${end}`;
  if (start) return `from ${start}`;
  return `until ${end}`;
}

export function DateRangePicker() {
  const start = useTimeRange((s) => s.start);
  const end = useTimeRange((s) => s.end);
  const preset = useTimeRange((s) => s.preset);
  const dataAsOf = useTimeRange((s) => s.dataAsOf);
  const setPreset = useTimeRange((s) => s.setPreset);
  const setCustom = useTimeRange((s) => s.setCustom);

  const [open, setOpen] = useState(false);
  const [draftStart, setDraftStart] = useState(start ?? "");
  const [draftEnd, setDraftEnd] = useState(end ?? "");
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Keep draft fields synced when the store changes outside the panel
  // (e.g. preset click, hydration from localStorage).
  useEffect(() => setDraftStart(start ?? ""), [start]);
  useEffect(() => setDraftEnd(end ?? ""), [end]);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const partial = isPartialPeriod(end, dataAsOf);

  const applyCustom = () => {
    if (draftStart && draftEnd) {
      setCustom(draftStart, draftEnd);
      setOpen(false);
    }
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
        className={cn(
          "tabular flex items-center gap-1.5 rounded-md px-2 py-1",
          "text-[0.68rem] font-medium ring-1 ring-inset ring-foreground/10",
          "bg-[color:var(--surface-1)] hover:bg-[color:var(--surface-2)]",
          "transition-colors",
        )}
      >
        <CalendarRange
          className="h-3 w-3 text-muted-foreground/70"
          strokeWidth={2}
        />
        <span className="text-muted-foreground/70 uppercase tracking-[0.06em]">
          Range
        </span>
        <span className="font-semibold text-foreground">
          {preset === "custom" ? formatRange(start, end) : labelOf(preset)}
        </span>
        {partial && (
          <span
            className="rounded px-1 py-0.5 text-[0.55rem] font-semibold uppercase tracking-wider text-[color:var(--warning)] bg-[color:var(--warning)]/10 ring-1 ring-inset ring-[color:var(--warning)]/30"
            title={`Window extends past dataset cutoff ${dataAsOf ?? "?"}`}
          >
            partial
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Date range picker"
          className={cn(
            "absolute right-0 top-full z-50 mt-1.5 w-72",
            "rounded-lg border border-border bg-card p-3",
            "shadow-lg ring-1 ring-inset ring-foreground/5",
            "animate-fade-up-1",
          )}
        >
          {/* Presets */}
          <div className="mb-3">
            <div className="mb-1.5 text-[0.6rem] uppercase tracking-[0.1em] text-muted-foreground/70">
              Quick range
            </div>
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    setPreset(p.id);
                    setOpen(false);
                  }}
                  className={cn(
                    "tabular rounded-md px-2 py-1 text-[0.7rem] font-medium",
                    "ring-1 ring-inset transition-colors",
                    preset === p.id
                      ? "bg-primary/15 text-primary ring-primary/40"
                      : "bg-[color:var(--surface-1)] text-muted-foreground hover:bg-[color:var(--surface-2)] ring-foreground/10",
                  )}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Custom range */}
          <div className="space-y-1.5 border-t border-border/60 pt-3">
            <div className="text-[0.6rem] uppercase tracking-[0.1em] text-muted-foreground/70">
              Custom
            </div>
            <div className="flex items-center gap-2">
              <input
                type="date"
                aria-label="Start date"
                value={draftStart}
                onChange={(e) => setDraftStart(e.target.value)}
                className="tabular flex-1 rounded-md border border-border bg-[color:var(--surface-1)] px-2 py-1 text-[0.72rem] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
              />
              <span className="text-muted-foreground/60 text-xs">→</span>
              <input
                type="date"
                aria-label="End date"
                value={draftEnd}
                onChange={(e) => setDraftEnd(e.target.value)}
                className="tabular flex-1 rounded-md border border-border bg-[color:var(--surface-1)] px-2 py-1 text-[0.72rem] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
              />
            </div>
            <Button
              type="button"
              size="sm"
              onClick={applyCustom}
              disabled={!draftStart || !draftEnd || draftStart > draftEnd}
              className="mt-1.5 h-7 w-full gap-1.5 text-[0.7rem]"
            >
              <Check className="h-3 w-3" strokeWidth={2.5} />
              Apply custom range
            </Button>
          </div>

          {dataAsOf && (
            <div className="mt-3 border-t border-border/60 pt-2 text-[0.6rem] text-muted-foreground/70 tabular">
              Data as of <span className="text-foreground">{dataAsOf}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function labelOf(preset: RangePreset): string {
  switch (preset) {
    case "7d":
      return "Last 7 days";
    case "30d":
      return "Last 30 days";
    case "90d":
      return "Last 90 days";
    case "365d":
      return "Last 1 year";
    case "all":
      return "All data";
    case "custom":
      return "Custom";
  }
}
