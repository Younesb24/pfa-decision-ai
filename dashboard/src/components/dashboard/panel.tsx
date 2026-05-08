"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface PanelProps {
  /** Anchor id, used as a scroll target. */
  id?: string;
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  /** Tag near the title (model name, count, etc.). */
  tag?: React.ReactNode;
  /** Optional footer row at the bottom of the panel. */
  footer?: React.ReactNode;
  className?: string;
  contentClassName?: string;
  children?: React.ReactNode;
  /** Animation delay utility class. */
  delay?: string;
}

/**
 * Compact section panel — replaces the heavier shadcn Card.
 * Slim header with icon + title + tag + action; no padding bloat.
 */
export function Panel({
  id,
  title,
  description,
  icon,
  action,
  tag,
  footer,
  className,
  contentClassName,
  children,
  delay,
}: PanelProps) {
  return (
    <section
      id={id}
      className={cn(
        "group/panel relative overflow-hidden rounded-xl bg-card scroll-mt-24",
        "border border-border/60 top-highlight",
        "transition-colors duration-200 hover:border-border-strong",
        delay,
        className
      )}
    >
      {(title || icon || action || tag) && (
        <header className="flex items-center justify-between gap-3 px-5 py-3 border-b border-border/60">
          <div className="flex items-center gap-2.5 min-w-0">
            {icon && (
              <div className="flex h-6 w-6 items-center justify-center text-muted-foreground shrink-0">
                {icon}
              </div>
            )}
            <div className="flex items-baseline gap-2.5 min-w-0">
              {title && (
                <h3 className="text-sm font-semibold tracking-tight text-foreground truncate">
                  {title}
                </h3>
              )}
              {description && (
                <p className="text-[0.7rem] text-muted-foreground/70 truncate hidden sm:block">
                  {description}
                </p>
              )}
            </div>
            {tag && <div className="shrink-0">{tag}</div>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}

      <div className={cn("px-5 py-4", contentClassName)}>{children}</div>

      {footer && (
        <footer className="px-5 py-2.5 border-t border-border/60 surface-1">
          {footer}
        </footer>
      )}
    </section>
  );
}
