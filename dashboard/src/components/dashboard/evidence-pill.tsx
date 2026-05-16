"use client";

import { cn } from "@/lib/utils";
import type { Evidence } from "@/lib/types";

interface EvidencePillProps {
  evidence: Evidence;
  className?: string;
}

export function EvidencePill({ evidence, className }: EvidencePillProps) {
  const display =
    typeof evidence.value === "number"
      ? evidence.unit
        ? `${evidence.value}${evidence.unit}`
        : evidence.value.toLocaleString()
      : String(evidence.value);

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md",
        "px-2.5 py-1 text-[0.72rem] font-medium",
        "bg-[color:var(--surface-1)] ring-1 ring-inset ring-foreground/10",
        "hover:ring-primary/30 transition-colors",
        className
      )}
      title={`Source: ${evidence.source}${evidence.as_of ? ` · as of ${evidence.as_of}` : ""}`}
    >
      <span className="text-muted-foreground">{evidence.metric}</span>
      <span className="text-foreground font-semibold tabular-nums">{display}</span>
      {evidence.as_of && (
        <span className="text-muted-foreground/60 text-[0.65rem]">
          {evidence.as_of}
        </span>
      )}
    </div>
  );
}
